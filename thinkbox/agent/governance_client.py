"""
KILO Cloud Agent — Governance Client

Handles admission checks, approval requests, audit logging, and token management.
"""

import asyncio
import time
import grpc
from typing import Optional, Dict, Any, List
import logging

from .protocol import governance_pb2, governance_pb2_grpc

logger = logging.getLogger(__name__)


class GovernanceClient:
    """Client for communicating with Governance services (Admission Gate, Approval, Token, Audit)."""

    def __init__(self, endpoint: str, agent_id: str, tenant_id: str):
        self.endpoint = endpoint
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[governance_pb2_grpc.GovernanceServiceStub] = None
        self._connected = False
        self._token_cache: Dict[str, str] = {}  # action_type -> token
        self._audit_buffer: List[governance_pb2.AuditEvent] = []
        self._audit_flush_task: Optional[asyncio.Task] = None
        self._audit_flush_interval = 1.0  # seconds
        self._audit_batch_size = 100

    async def connect(self):
        """Establish gRPC connection to governance service."""
        self._channel = grpc.aio.insecure_channel(self.endpoint)
        self._stub = governance_pb2_grpc.GovernanceServiceStub(self._channel)
        
        try:
            await asyncio.wait_for(self._channel.channel_ready(), timeout=10.0)
            self._connected = True
            self._audit_flush_task = asyncio.create_task(self._audit_flush_loop())
            logger.info(f"Governance client connected to {self.endpoint}")
        except asyncio.TimeoutError:
            logger.error(f"Governance connection timeout: {self.endpoint}")
            raise

    async def close(self):
        """Close connection and flush audit buffer."""
        await self._flush_audit_buffer()
        if self._audit_flush_task:
            self._audit_flush_task.cancel()
        if self._channel:
            await self._channel.close()
        self._connected = False

    # ============================================================
    # Admission Gate
    # ============================================================

    async def check_admission(
        self,
        action_type: str,
        action_spec: Dict[str, Any],
        task_id: Optional[str] = None,
        governance_token: Optional[str] = None,
    ) -> governance_pb2.AdmissionDecision:
        """
        Check admission for an action. Fail-closed on timeout/error.
        """
        if not self._connected:
            logger.warning("Governance not connected, denying admission (fail-closed)")
            return governance_pb2.AdmissionDecision(
                decision_id="",
                allowed=False,
                reason="Governance service unavailable",
                conditions=[],
            )

        # Use cached token if available and not provided
        if governance_token is None:
            governance_token = self._token_cache.get(action_type, "")

        request = governance_pb2.AdmissionRequest(
            agent_id=self.agent_id,
            task_id=task_id or "",
            action_type=action_type,
            action_spec=self._dict_to_struct(action_spec),
            governance_token=governance_token,
            tenant_id=self.tenant_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        try:
            # Short timeout for admission (fail-fast)
            decision = await asyncio.wait_for(
                self._stub.CheckAdmission(request),
                timeout=5.0,
            )
            
            # Cache token if issued
            if decision.allowed and decision.governance_token:
                self._token_cache[action_type] = decision.governance_token
            
            # Emit audit event (async, non-blocking)
            await self.emit_audit_event(
                event_type="admission.decided",
                payload={
                    "decision_id": decision.decision_id,
                    "allowed": decision.allowed,
                    "reason": decision.reason,
                    "governance_token_hash": self._hash_token(decision.governance_token) if decision.governance_token else "",
                    "policy_version": "v1.0",
                    "evaluation_ms": 0,
                },
                task_id=task_id,
            )
            
            return decision
            
        except asyncio.TimeoutError:
            logger.error(f"Admission check timeout for {action_type}")
            return governance_pb2.AdmissionDecision(
                decision_id="",
                allowed=False,
                reason="Admission gate timeout",
                conditions=[],
            )
        except Exception as e:
            logger.error(f"Admission check error: {e}")
            return governance_pb2.AdmissionDecision(
                decision_id="",
                allowed=False,
                reason=f"Admission check failed: {e}",
                conditions=[],
            )

    # ============================================================
    # Approval Requests
    # ============================================================

    async def request_approval(
        self,
        action_type: str,
        action_spec: Dict[str, Any],
        gate_type: str = "HUMAN",
        expires_in_seconds: int = 3600,
        priority: str = "NORMAL",
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> governance_pb2.ApprovalDecision:
        """Request approval for an action."""
        if not self._connected:
            return governance_pb2.ApprovalDecision(
                decision_id="",
                request_id="",
                decided_by="",
                decided_at="",
                decision=governance_pb2.ApprovalDecisionType.DENIED,
                reason="Governance service unavailable",
            )

        request = governance_pb2.ApprovalRequest(
            request_id=str(time.time_ns()),
            agent_id=self.agent_id,
            task_id=task_id or "",
            action_type=action_type,
            action_spec=self._dict_to_struct(action_spec),
            gate_type=governance_pb2.GateType.Value(gate_type),
            expires_at=time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", 
                time.gmtime(time.time() + expires_in_seconds)
            ),
            priority=governance_pb2.ApprovalRequest.Priority.Value(priority),
            context=self._dict_to_struct(context or {}),
        )

        try:
            decision = await self._stub.RequestApproval(request)
            
            if decision.decision == governance_pb2.ApprovalDecisionType.APPROVED:
                self._token_cache[action_type] = decision.governance_token
            
            return decision
            
        except Exception as e:
            logger.error(f"Approval request error: {e}")
            return governance_pb2.ApprovalDecision(
                decision_id="",
                request_id="",
                decided_by="",
                decided_at="",
                decision=governance_pb2.ApprovalDecisionType.DENIED,
                reason=f"Approval request failed: {e}",
            )

    async def get_approval_status(self, request_id: str) -> governance_pb2.ApprovalDecision:
        """Get status of a pending approval request."""
        request = governance_pb2.ApprovalStatusRequest(request_id=request_id)
        return await self._stub.GetApprovalStatus(request)

    # ============================================================
    # Token Management
    # ============================================================

    async def request_token(
        self,
        action_type: str,
        ttl_seconds: int = 300,
        task_id: Optional[str] = None,
    ) -> str:
        """Request a governance token for an action type."""
        if not self._connected:
            return ""

        # Check cache first
        if action_type in self._token_cache:
            return self._token_cache[action_type]

        request = governance_pb2.TokenRequest(
            agent_id=self.agent_id,
            task_id=task_id or "",
            action_type=action_type,
            tenant_id=self.tenant_id,
            ttl_seconds=ttl_seconds,
        )

        try:
            response = await self._stub.RequestToken(request)
            if response.token:
                self._token_cache[action_type] = response.token
                return response.token
        except Exception as e:
            logger.error(f"Token request error: {e}")
        
        return ""

    async def revoke_token(self, token_id: str, reason: str = "") -> bool:
        """Revoke a governance token."""
        request = governance_pb2.TokenRevocationRequest(token_id=token_id, reason=reason)
        try:
            response = await self._stub.RevokeToken(request)
            # Clear from cache
            for action_type, token in list(self._token_cache.items()):
                if token_id in token:
                    del self._token_cache[action_type]
            return response.revoked
        except Exception as e:
            logger.error(f"Token revocation error: {e}")
            return False

    # ============================================================
    # Audit Logging
    # ============================================================

    async def emit_audit_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
    ):
        """Emit an audit event (buffered, async flush)."""
        event = governance_pb2.AuditEvent(
            event_id=str(time.time_ns()),
            event_type=event_type,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            agent_id=self.agent_id,
            task_id=task_id or "",
            tenant_id=self.tenant_id,
            correlation_id=correlation_id or "",
            causation_id=causation_id or "",
            payload=self._dict_to_struct(payload),
            metadata=self._dict_to_struct({
                "agent_version": "1.0.0",
                "protocol_version": "1.0",
            }),
        )
        
        self._audit_buffer.append(event)
        
        # Flush if buffer full
        if len(self._audit_buffer) >= self._audit_batch_size:
            await self._flush_audit_buffer()

    async def emit_audit_batch(self, events: List[Dict[str, Any]]):
        """Emit multiple audit events at once."""
        audit_events = []
        for e in events:
            audit_events.append(governance_pb2.AuditEvent(
                event_id=e.get("event_id", str(time.time_ns())),
                event_type=e.get("event_type", "unknown"),
                timestamp=e.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                agent_id=e.get("agent_id", self.agent_id),
                task_id=e.get("task_id", ""),
                tenant_id=e.get("tenant_id", self.tenant_id),
                correlation_id=e.get("correlation_id", ""),
                causation_id=e.get("causation_id", ""),
                payload=self._dict_to_struct(e.get("payload", {})),
                metadata=self._dict_to_struct(e.get("metadata", {})),
            ))
        
        if audit_events:
            batch = governance_pb2.AuditEventBatch(events=audit_events)
            try:
                await self._stub.EmitAuditBatch(batch)
            except Exception as e:
                logger.error(f"Audit batch emit error: {e}")

    async def _flush_audit_buffer(self):
        """Flush buffered audit events to governance service."""
        if not self._audit_buffer or not self._connected:
            return
        
        events = self._audit_buffer[:self._audit_batch_size]
        self._audit_buffer = self._audit_buffer[self._audit_batch_size:]
        
        try:
            batch = governance_pb2.AuditEventBatch(events=events)
            await self._stub.EmitAuditBatch(batch)
        except Exception as e:
            logger.error(f"Audit flush error: {e}")
            # Re-add to buffer for retry
            self._audit_buffer = events + self._audit_buffer

    async def _audit_flush_loop(self):
        """Periodic audit buffer flush."""
        while self._connected:
            try:
                await asyncio.sleep(self._audit_flush_interval)
                await self._flush_audit_buffer()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit flush loop error: {e}")

    # ============================================================
    # Policy Evaluation
    # ============================================================

    async def evaluate_policy(
        self,
        policy_version: str,
        input_data: Dict[str, Any],
    ) -> governance_pb2.PolicyEvaluationResponse:
        """Evaluate policy via OPA."""
        request = governance_pb2.PolicyEvaluationRequest(
            policy_version=policy_version,
            input=self._dict_to_struct(input_data),
        )
        return await self._stub.EvaluatePolicy(request)

    # ============================================================
    # Helpers
    # ============================================================

    def _dict_to_struct(self, data: Dict[str, Any]) -> Any:
        """Convert dict to protobuf Struct."""
        from google.protobuf import struct_pb2
        struct = struct_pb2.Struct()
        struct.update(data)
        return struct

    def _hash_token(self, token: str) -> str:
        """Hash token for audit logging."""
        import hashlib
        return f"sha256:{hashlib.sha256(token.encode()).hexdigest()[:16]}"

    @property
    def connected(self) -> bool:
        return self._connected
"""Unit tests for thinkbox/marketplace — Agent Marketplace."""

import json
import os
import tempfile
import unittest

from thinkbox.marketplace import (
    AgentPackageManifest,
    InstallError,
    PackageDependency,
    PackageEntryPoint,
    PackageInstaller,
    PackagePublisher,
    PackageRegistry,
    PublishError,
    PublishRecord,
    ValidationError,
)


def _make_manifest(
    name: str = "test-agent",
    version: str = "1.0.0",
    **kwargs,
) -> AgentPackageManifest:
    defaults = dict(
        description="Test agent",
        entry_points=[
            PackageEntryPoint(
                module="thinkbox.agents.test", attribute="Agent"
            )
        ],
        capabilities=["file:read", "task:execute"],
    )
    defaults.update(kwargs)
    return AgentPackageManifest(name=name, version=version, **defaults)


class TestPackageDependency(unittest.TestCase):
    def test_matches_wildcard(self):
        dep = PackageDependency("foo")
        self.assertTrue(dep.matches("1.0.0"))
        self.assertTrue(dep.matches("2.3.4"))

    def test_matches_exact(self):
        dep = PackageDependency("foo", "1.0.0")
        self.assertTrue(dep.matches("1.0.0"))
        self.assertFalse(dep.matches("1.0.1"))

    def test_matches_gte(self):
        dep = PackageDependency("foo", ">=1.0.0")
        self.assertTrue(dep.matches("1.0.0"))
        self.assertTrue(dep.matches("1.5.0"))
        self.assertFalse(dep.matches("0.9.0"))

    def test_matches_gt(self):
        dep = PackageDependency("foo", ">1.0.0")
        self.assertTrue(dep.matches("1.0.1"))
        self.assertFalse(dep.matches("1.0.0"))

    def test_matches_lt(self):
        dep = PackageDependency("foo", "<2.0.0")
        self.assertTrue(dep.matches("1.0.0"))
        self.assertFalse(dep.matches("2.0.0"))

    def test_matches_optional(self):
        dep = PackageDependency("foo", optional=True)
        self.assertTrue(dep.optional)

    def test_to_dict_and_from_dict(self):
        dep = PackageDependency("foo", ">=1.0", optional=True)
        d = dep.to_dict()
        restored = PackageDependency.from_dict(d)
        self.assertEqual(restored.name, "foo")
        self.assertEqual(restored.version_spec, ">=1.0")
        self.assertTrue(restored.optional)


class TestPackageEntryPoint(unittest.TestCase):
    def test_to_dict_and_from_dict(self):
        ep = PackageEntryPoint("mod", "attr", "desc")
        d = ep.to_dict()
        restored = PackageEntryPoint.from_dict(d)
        self.assertEqual(restored.module, "mod")
        self.assertEqual(restored.attribute, "attr")
        self.assertEqual(restored.description, "desc")


class TestAgentPackageManifest(unittest.TestCase):
    def test_id(self):
        m = _make_manifest()
        self.assertEqual(m.id, "test-agent@1.0.0")

    def test_compute_hash(self):
        m = _make_manifest()
        h = m.compute_hash()
        self.assertEqual(len(h), 32)
        self.assertEqual(h, m.package_hash) if m.package_hash else None

    def test_verify_hash_true(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        self.assertTrue(m.verify_hash())

    def test_verify_hash_false(self):
        m = _make_manifest()
        m.package_hash = "bad"
        self.assertFalse(m.verify_hash())

    def test_verify_hash_empty(self):
        m = _make_manifest()
        self.assertFalse(m.verify_hash())

    def test_to_dict_and_from_dict(self):
        m = _make_manifest(
            description="",
            author="dev",
            license="MIT",
            tags=["test", "agent"],
            metadata={"key": "val"},
        )
        d = m.to_dict()
        restored = AgentPackageManifest.from_dict(d)
        self.assertEqual(restored.name, "test-agent")
        self.assertEqual(restored.version, "1.0.0")
        self.assertEqual(restored.author, "dev")
        self.assertEqual(restored.license, "MIT")
        self.assertEqual(restored.tags, ["test", "agent"])
        self.assertEqual(restored.metadata, {"key": "val"})

    def test_to_json_and_from_json(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        text = m.to_json()
        restored = AgentPackageManifest.from_json(text)
        self.assertEqual(restored.name, m.name)
        self.assertEqual(restored.version, m.version)

    def test_minimum_manifest(self):
        m = AgentPackageManifest(name="x", version="1.0.0")
        self.assertEqual(m.id, "x@1.0.0")
        self.assertEqual(m.description, "")
        self.assertEqual(m.entry_points, [])


class TestPackageRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = PackageRegistry()
        self.manifest = _make_manifest()
        self.manifest.package_hash = self.manifest.compute_hash()

    def test_available_count_empty(self):
        self.assertEqual(self.registry.available_count, 0)

    def test_register_available(self):
        self.registry.register_available(self.manifest)
        self.assertEqual(self.registry.available_count, 1)
        self.assertEqual(self.registry.get_available(self.manifest.id), self.manifest)

    def test_register_available_batch(self):
        manifests = [self.manifest, _make_manifest(name="a2")]
        count = self.registry.register_available_batch(manifests)
        self.assertEqual(count, 2)
        self.assertEqual(self.registry.available_count, 2)

    def test_install(self):
        self.registry.register_available(self.manifest)
        installed = self.registry.install(self.manifest.id, "/path/to/agent")
        self.assertEqual(installed.manifest.id, self.manifest.id)
        self.assertEqual(installed.status, "installed")
        self.assertTrue(self.registry.is_installed(self.manifest.id))

    def test_install_not_found(self):
        with self.assertRaises(ValueError):
            self.registry.install("missing", "/path")

    def test_install_already_installed(self):
        self.registry.register_available(self.manifest)
        self.registry.install(self.manifest.id, "/path1")
        with self.assertRaises(ValueError):
            self.registry.install(self.manifest.id, "/path2")

    def test_uninstall(self):
        self.registry.register_available(self.manifest)
        self.registry.install(self.manifest.id, "/path")
        self.assertTrue(self.registry.uninstall(self.manifest.id))
        self.assertFalse(self.registry.is_installed(self.manifest.id))

    def test_uninstall_not_found(self):
        self.assertFalse(self.registry.uninstall("missing"))

    def test_list_installed(self):
        self.registry.register_available(self.manifest)
        self.registry.register_available(_make_manifest(name="a2"))
        self.registry.install(self.manifest.id, "/path1")
        installed = self.registry.list_installed()
        self.assertEqual(len(installed), 1)

    def test_list_available(self):
        self.registry.register_available(self.manifest)
        self.registry.register_available(_make_manifest(name="a2"))
        self.assertEqual(len(self.registry.list_available()), 2)

    def test_search(self):
        self.registry.register_available(self.manifest)
        self.registry.register_available(
            _make_manifest(name="other", description="database tool")
        )
        result = self.registry.search("test")
        self.assertEqual(result.total, 1)

    def test_search_by_capability(self):
        self.registry.register_available(self.manifest)
        result = self.registry.search("file:read")
        self.assertEqual(result.total, 1)

    def test_get_installed(self):
        self.registry.register_available(self.manifest)
        self.registry.install(self.manifest.id, "/path")
        result = self.registry.get_installed(self.manifest.id)
        self.assertIsNotNone(result)
        self.assertEqual(result.install_path, "/path")

    def test_get_history(self):
        self.registry.register_available(self.manifest)
        self.registry.register_available(_make_manifest(name="a2"))
        history = self.registry.get_history()
        self.assertEqual(len(history), 2)


class TestPackageInstaller(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.registry = PackageRegistry()
        self.installer = PackageInstaller(self.registry, base_path=self.tmpdir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_validate_valid(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        errors = self.installer.validate(m)
        self.assertEqual(errors, [])

    def test_validate_missing_name(self):
        m = AgentPackageManifest(name="", version="1.0.0")
        errors = self.installer.validate(m)
        self.assertTrue(any("name" in e.lower() for e in errors))

    def test_validate_missing_version(self):
        m = AgentPackageManifest(name="test", version="")
        errors = self.installer.validate(m)
        self.assertTrue(any("version" in e.lower() for e in errors))

    def test_validate_bad_version(self):
        m = AgentPackageManifest(name="test", version="not-semver")
        errors = self.installer.validate(m)
        self.assertTrue(any("version" in e.lower() for e in errors))

    def test_validate_no_entry_points(self):
        m = AgentPackageManifest(name="test", version="1.0.0")
        errors = self.installer.validate(m)
        self.assertTrue(any("entry" in e.lower() for e in errors))

    def test_install_valid(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        installed = self.installer.install(m)
        self.assertEqual(installed.manifest.id, m.id)
        self.assertEqual(installed.status, "installed")
        self.assertTrue(os.path.isdir(installed.install_path))

    def test_install_validation_error(self):
        m = AgentPackageManifest(name="", version="")
        with self.assertRaises(ValidationError):
            self.installer.install(m)

    def test_install_already_installed(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        self.installer.install(m)
        with self.assertRaises(InstallError):
            self.installer.install(m)

    def test_install_from_dict(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        installed = self.installer.install_from_dict(m.to_dict())
        self.assertEqual(installed.manifest.id, m.id)

    def test_install_from_json(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        text = m.to_json()
        installed = self.installer.install_from_json(text)
        self.assertEqual(installed.manifest.id, m.id)

    def test_uninstall(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        self.installer.install(m)
        self.assertTrue(self.installer.uninstall(m.id))
        self.assertFalse(self.registry.is_installed(m.id))

    def test_uninstall_not_found(self):
        self.assertFalse(self.installer.uninstall("missing"))

    def test_list_installed(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        self.installer.install(m)
        self.assertEqual(len(self.installer.list_installed()), 1)

    def test_get_install_log(self):
        m = _make_manifest()
        m.package_hash = m.compute_hash()
        self.installer.install(m)
        log = self.installer.get_install_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]["action"], "install")


class TestPackagePublisher(unittest.TestCase):
    def setUp(self):
        self.registry = PackageRegistry()
        self.publisher = PackagePublisher(self.registry, signing_key="test-key")

    def test_publish(self):
        m = _make_manifest()
        published = self.publisher.publish(m)
        self.assertEqual(published.id, m.id)
        self.assertIsNotNone(published.package_hash)
        self.assertIsNotNone(published.signed_by)
        self.assertTrue(self.publisher.verify_signature(published))

    def test_publish_no_sign(self):
        m = _make_manifest()
        published = self.publisher.publish(m, sign=False)
        self.assertIsNone(published.signed_by)

    def test_publish_adds_to_registry(self):
        m = _make_manifest()
        self.publisher.publish(m)
        self.assertEqual(self.publisher.registry.available_count, 1)

    def test_publish_count(self):
        m = _make_manifest()
        self.publisher.publish(m)
        self.assertEqual(self.publisher.published_count, 1)

    def test_update(self):
        m = _make_manifest()
        self.publisher.publish(m)
        m2 = _make_manifest(name="test-agent", version="1.0.0")
        updated = self.publisher.update(m2)
        self.assertEqual(updated.id, m.id)
        self.assertEqual(self.publisher.published_count, 2)

    def test_update_not_found(self):
        m = _make_manifest()
        with self.assertRaises(PublishError):
            self.publisher.update(m)

    def test_deprecate(self):
        m = _make_manifest()
        self.publisher.publish(m)
        self.assertTrue(self.publisher.deprecate(m.id))

    def test_deprecate_not_found(self):
        self.assertFalse(self.publisher.deprecate("missing"))

    def test_verify_signature_true(self):
        m = _make_manifest()
        published = self.publisher.publish(m)
        self.assertTrue(self.publisher.verify_signature(published))

    def test_verify_signature_false(self):
        m = _make_manifest()
        self.registry.register_available(m)
        self.assertFalse(self.publisher.verify_signature(m))

    def test_list_published(self):
        m = _make_manifest()
        self.publisher.publish(m)
        records = self.publisher.list_published()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].action, "publish")

    def test_get_publish_history(self):
        m = _make_manifest()
        self.publisher.publish(m)
        self.publisher.publish(m)
        history = self.publisher.get_publish_history(m.id)
        self.assertEqual(len(history), 2)

    def test_publish_record_has_timestamp(self):
        m = _make_manifest()
        published = self.publisher.publish(m)
        record = self.publisher.list_published()[0]
        self.assertGreater(record.timestamp, 0)


class TestPackageIntegration(unittest.TestCase):
    def test_publish_then_install(self):
        registry = PackageRegistry()
        publisher = PackagePublisher(registry)
        installer = PackageInstaller(registry)
        m = _make_manifest()
        publisher.publish(m)
        installed = installer.install(m)
        self.assertEqual(installed.manifest.id, m.id)

    def test_publish_search_install(self):
        registry = PackageRegistry()
        publisher = PackagePublisher(registry)
        installer = PackageInstaller(registry)
        m = _make_manifest(name="compute-agent", tags=["compute"])
        publisher.publish(m)
        result = registry.search("compute")
        self.assertEqual(result.total, 1)
        installed = installer.install(result.packages[0])
        self.assertEqual(installed.manifest.name, "compute-agent")

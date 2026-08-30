#!/bin/bash
PASSWORD=$1
HOST=$2
shift 2
COMMAND="$@"
{
  sleep 1
  echo "$PASSWORD"
  sleep 1
} | ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -tt root@$HOST "$COMMAND" 2>&1

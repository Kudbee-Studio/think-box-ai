# Think Box AI — operator shortcuts (enterprise)
.PHONY: test spine docker-contract docker-build docker-up docker-hermetic

test:
	python3 -m unittest discover -s tests -t .

spine:
	PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py

docker-contract:
	python3 scripts/verify_docker_contract.py

docker-build:
	docker build -t thinkbox-ai:local -f Dockerfile .

docker-build-hermetic:
	docker build -t thinkbox-ai:hermetic -f Dockerfile.hermetic .

docker-up:
	docker compose up api -d --build

docker-hermetic:
	docker compose --profile hermetic run --rm spine-verify

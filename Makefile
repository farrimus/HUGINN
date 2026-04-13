.PHONY: test build-frontend dev

test:
	python3 -m pytest tests/ -q

build-frontend:
	cd frontend && npm run build

dev:
	uvicorn main:app --reload --port 8745

.PHONY: install run dev test lint format clean diagnosis-api diagnosis-api-dev

# Install dependencies
install:
	pip install -r requirements.txt

# Run the agent (OpenAI version)
run: stop
	python app.py dev

# Run in development mode with auto-reload (OpenAI version)
dev: stop
	python app.py dev --reload

# Run Gemini Realtime agent
gemini: stop
	python gemini_realtime_agent.py dev

# Run Gemini in development mode with auto-reload
gemini-dev: stop
	python gemini_realtime_agent.py dev --reload

# Stop all agent processes
stop:
	@echo "Stopping all agent processes..."
	@pkill -f "python.*app.py" || true
	@pkill -f "python.*basic_agent" || true
	@pkill -f "multiprocessing.*spawn" || true
	@sleep 1
	@echo "All agents stopped."

# Run tests
test:
	pytest tests/ -v

# Lint code
lint:
	ruff check .

# Format code
format:
	ruff format .

# Clean cache files
clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -delete
	find . -type d -name '.pytest_cache' -delete
	find . -type d -name '.ruff_cache' -delete

# Run diagnosis API server
diagnosis-api:
	python diagnosis_api.py

# Run diagnosis API in development mode
diagnosis-api-dev:
	uvicorn diagnosis_api:app --reload --host 0.0.0.0 --port 8000

# Run pydantic diagnosis agent
pydantic-diagnosis:
	python pydantic_diagnosis_agent.py

# Run pydantic diagnosis agent in development mode
pydantic-diagnosis-dev:
	uvicorn pydantic_diagnosis_agent:app --reload --host 0.0.0.0 --port 8000
# FastAPI Project

A simple REST API built with **FastAPI** and **Python**.

## Technologies

* Python
* FastAPI
* Uvicorn
* UV

## Setup

Clone the repository and navigate to the project directory:

```bash
git clone <your-repository-url>
cd <your-project-folder>
```

Install the project dependencies using UV:

```bash
uv sync
```

## Run the Application

Start the FastAPI application with:

```bash
uv run uvicorn main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

## API Documentation

FastAPI automatically provides interactive API documentation.

**Swagger UI**

http://127.0.0.1:8000/docs

**ReDoc**

http://127.0.0.1:8000/redoc

## Project Structure

```text
.
├── main.py
├── pyproject.toml
├── uv.lock
├── .python-version
├── .gitignore
└── README.md
```

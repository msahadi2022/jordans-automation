# Current Feature: Fabric Connection & Data Pipeline Setup

## Status

Not Started

## Goals

- Connect to Microsoft Fabric Gold via ODBC Driver 18 for SQL Server
- Authenticate using `azure-identity` (Device Code flow for dev; Service Principal for prod — switchable via config flag)
- Execute the Jordan orders SQL query joining `SALESDOC_HEADER`, `SALESDOC_DETAIL`, and `WDS_Items_Current`
- Validate results — detect and log missing SKUs, null volumes, and null weights
- All configurable values (endpoint, tenant ID, customer numbers, batch values) read from `config.json` — nothing hardcoded
- Every run produces a structured JSON log entry
- Retry connection once after 60 seconds on failure, then send admin alert

## Notes

- Virtual environment: `~/fabric-env` — `pyodbc`, `azure-identity`, `requests` already installed
- ODBC Driver 18 for SQL Server (`msodbcsql18`) already installed on machine
- Fabric endpoint and tenant ID confirmed working from research phase
- Connection uses Azure AD token injection via `attrs_before={1256: token_struct}`
- Auth must support swapping Device Code → ClientSecretCredential via config flag without changing core logic
- This is `fabric_client.py` — the foundation all other modules depend on; build and test this first
- Full spec detail in `context/features/task-01-fabric-connection.md`

## History

- Project setup and boilerplate cleanup

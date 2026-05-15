# Fabric Connection & Data Pipeline Setup

## Overview

Set up the Microsoft Fabric Gold connection, Azure AD authentication, and core SQL query that powers the Jordan Brand container automation.

## Requirements

- Connect to Microsoft Fabric Gold via ODBC Driver 18 for SQL Server
- Use `azure-identity` for Azure AD authentication
- Use Device Code flow for development; plan for Service Principal in production
- Execute the Jordan orders SQL query across `SALESDOC_HEADER`, `SALESDOC_DETAIL`, and `WDS_Items_Current`
- Validate results — detect and log missing SKUs, null volumes, null weights
- All configurable values (endpoint, tenant ID, customer numbers, batch values) must be read from `config.json` — never hardcoded
- Every run must produce a structured JSON log entry
- Retry connection once after 60 seconds on failure, then alert admin

## References

- Full spec: `@feature-spec-05-fabric-connection.md`
- Project overview: `@jordan-automation-project-overview.md`
- Config structure: defined in Spec 05

## Notes

The virtual environment is at `~/fabric-env`. Dependencies (`pyodbc`, `azure-identity`, `requests`) are already installed there. Use this environment.

The ODBC Driver 18 for SQL Server (`msodbcsql18`) is already installed on the machine.

Fabric endpoint and tenant ID are confirmed working — tested during research phase. See Spec 05 for the exact connection string and token injection pattern using `attrs_before={1256: token_struct}`.

Production auth will use a Service Principal — design the auth module to support swapping from Device Code to ClientSecretCredential via a config flag without changing core logic.

This module (`fabric_client.py`) is the foundation all other specs depend on. Build and test this first.

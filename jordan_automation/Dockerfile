FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# Install ODBC Driver 18 for SQL Server
RUN apt-get update \
    && apt-get install -y curl gnupg2 \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Azure Functions runtime expects app code in /home/site/wwwroot
COPY . /home/site/wwwroot

# Install Python dependencies
RUN cd /home/site/wwwroot \
    && pip install --no-cache-dir -r requirements.txt

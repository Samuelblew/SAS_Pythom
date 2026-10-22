# IAS — Backend

API Python (FastAPI) do Intelligent Allocation System.

## Local

```powershell
cd Backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # preencha a senha do MySQL
uvicorn app.main:app --host 127.0.0.1 --port 5203
```

Swagger: http://localhost:5203/swagger  
Health: `GET /api/v1/health`

Ou use `rodar-swagger.bat` / `rodar-site.bat` na raiz.

## Produção (AWS)

Imagem Docker na raiz do repositório. Guia: `docs/DEPLOY-AWS.txt`.

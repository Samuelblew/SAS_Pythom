# IAS local com Docker

## Arquitetura

```text
Navegador → localhost:5173 → frontend (Nginx + React)
                             └─ /api/ e /swagger → backend:8080 (FastAPI)
                                                    └─ db:3306 (MySQL)
Swagger direto → localhost:5203/swagger ─────────────┘
```

Backend e API são a mesma aplicação neste projeto. Portanto existem três
containers: frontend, backend/API e banco de dados.

## Iniciar

Abra o Docker Desktop e, no PowerShell dentro da pasta do projeto, rode:

```powershell
docker compose up -d --build --wait
docker compose ps
```

Na primeira execução, o Docker baixa as imagens e instala as dependências.
O frontend passa pela compilação TypeScript e Vite. O Compose aguarda o banco
responder a uma consulta SQL antes de iniciar a API, e aguarda a saúde da API
antes de iniciar o frontend.

## Primeiro acesso

1. Abra http://localhost:5203/swagger.
2. Em `POST /api/v1/tenants`, use **Try it out**, preencha o corpo conforme o
   exemplo do Swagger com o nome do seu ambiente e execute.
3. Copie o `id` da resposta.
4. Abra http://localhost:5173 e informe esse ID na configuração de tenant do site.

O banco começa vazio: pessoas, projetos e competências devem ser cadastrados.
Os dados do MySQL do Windows não são copiados para o container.

Cada instalação cria seus próprios tenants. Não use IDs de outra máquina;
informe o ID retornado no seu Swagger no menu de engrenagem do cabeçalho.

## Operação

```powershell
docker compose logs --tail 100 backend
docker compose logs --tail 100 db
docker compose down
docker compose up -d --build --wait
```

`down` preserva o volume do banco. **`docker compose down -v` apaga os dados
deste ambiente Docker** e só deve ser usado quando quiser reiniciá-lo do zero.

Se uma porta estiver ocupada, altere o lado esquerdo do mapeamento no
`compose.yaml`, por exemplo `127.0.0.1:5174:80` para o frontend.

As senhas e a chave JWT presentes no Compose são exclusivas do ambiente local.
Não use essa configuração como configuração de produção.

Referência: [ordem de inicialização do Docker Compose](https://docs.docker.com/compose/how-tos/startup-order/).

## Teste isolado com banco novo

No PowerShell, use um nome de projeto e portas diferentes para preservar o
ambiente principal. Python 3.11 ou superior é necessário apenas para executar
o script de teste no computador.

```powershell
$env:IAS_WEB_PORT='15173'
$env:IAS_API_PORT='15203'
docker compose -p ias-validation up -d --build --wait --wait-timeout 240
python scripts/test-integration.py --base-url http://127.0.0.1:15173 --state-file "$env:TEMP/ias-test-state.json"
docker compose -p ias-validation restart db backend
docker compose -p ias-validation up -d --wait --wait-timeout 240
python scripts/test-integration.py --base-url http://127.0.0.1:15173 --state-file "$env:TEMP/ias-test-state.json" --verify-state
```

Após os testes, remova somente o ambiente de validação e seu banco descartável:

```powershell
docker compose -p ias-validation down -v
Remove-Item Env:IAS_WEB_PORT, Env:IAS_API_PORT
```

O workflow `.github/workflows/docker-integration.yml` reproduz esse processo
em um runner novo do GitHub Actions.

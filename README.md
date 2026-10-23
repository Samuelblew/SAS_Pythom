# IAS — Intelligent Allocation System

Ferramenta de gerenciamento para **gerentes de projetos** planejarem equipes e acompanharem a alocação de profissionais. O IAS reúne pessoas, competências, clientes e projetos para ajudar o gerente a identificar disponibilidade, distribuir trabalho, evitar sobrecarga e acompanhar custos e capacidade futura.

## O que o sistema oferece

- Cadastro de profissionais, competências, clientes e projetos.
- Alocação de pessoas por período e percentual de dedicação.
- Controle de indisponibilidades e bloqueio de sobrealocação.
- Visões de capacidade, profissionais disponíveis e necessidades dos projetos.
- Sugestões de profissionais por critérios determinísticos de compatibilidade.
- Indicadores financeiros, simulações e histórico de alterações.
- Separação dos dados por organização (tenant).

## Instalação rápida com Docker

### 1. Pré-requisitos

Instale [Git](https://git-scm.com/downloads) e [Docker Desktop](https://www.docker.com/products/docker-desktop/). No Windows, habilite o WSL 2 solicitado pelo instalador e use containers Linux. Abra o Docker Desktop e aguarde o motor iniciar.

Confira no terminal:

```powershell
git --version
docker version
docker compose version
```

Não é necessário instalar Python, Node.js ou MySQL no computador para rodar a aplicação pelo Docker.

### 2. Baixar o projeto

```powershell
git clone https://github.com/Samuelblew/SAS_Pythom.git
cd SAS_Pythom
```

Também é possível baixar o ZIP pelo GitHub, extrair e abrir um terminal na pasta que contém `compose.yaml`.

### 3. Construir e iniciar

```powershell
docker compose up -d --build --wait --wait-timeout 240
docker compose ps
```

A primeira execução baixa as imagens e instala as dependências; pode levar alguns minutos. Ao terminar, `frontend`, `backend` e `db` devem aparecer como **healthy**.

| Acesso | Endereço |
|---|---|
| Aplicação | http://localhost:5173 |
| Documentação interativa da API (Swagger) | http://localhost:5203/swagger |
| Verificação de saúde e conexão ao banco | http://localhost:5203/api/v1/health |

### 4. Criar sua organização

O banco é criado automaticamente e começa vazio. Cada instalação gera seus próprios IDs: não é necessário copiar arquivos `.env` nem usar um ID de outra máquina.

1. Abra o Swagger e localize `POST /api/v1/tenants`.
2. Clique em **Try it out** e envie:

```json
{"name": "Minha organizacao"}
```

3. Clique em **Execute** e copie o campo `id` da resposta HTTP 201.
4. Abra o site, clique na **engrenagem** no cabeçalho e cole o ID no campo **Tenant**.
5. Cadastre competências, profissionais e clientes; depois crie projetos e suas alocações.

Alternativa no PowerShell para criar a organização:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5203/api/v1/tenants -ContentType 'application/json' -Body '{"name":"Minha organizacao"}'
```

Use um nome diferente para cada organização. O navegador guarda o Tenant ID localmente; outro navegador precisa receber o mesmo ID para acessar os mesmos dados.

## Como funciona

```text
Navegador → frontend (React + Nginx, porta 5173)
               └─ /api/ → backend/API (FastAPI, porta 5203)
                              └─ MySQL 8 (rede interna Docker)
```

A API faz parte do backend. São três containers, iniciados pelo Docker Compose com verificações de saúde. O banco fica em um volume persistente e não precisa de MySQL instalado no Windows.

| Parte | Tecnologias |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Backend/API | Python 3.12, FastAPI, SQLAlchemy |
| Banco | MySQL 8 |
| Execução local | Docker Compose e Nginx |

## Parar, atualizar e consultar logs

Execute sempre na pasta do projeto:

```powershell
docker compose down                 # Para sem apagar os dados
docker compose up -d --wait          # Inicia novamente
docker compose logs --tail 100 backend
docker compose logs --tail 100 db
```

Para atualizar uma instalação feita com Git:

```powershell
git pull
docker compose up -d --build --wait --wait-timeout 240
```

**`docker compose down -v` apaga o banco deste ambiente.** Use apenas se quiser começar do zero; depois será necessário criar a organização novamente.

## Testes e integração contínua

A pipeline do GitHub Actions executa:

- **Frontend CI:** instalação com lockfile, lint, 22 testes e build.
- **Backend CI:** instalação das dependências e compilação Python.
- **Docker Integration:** construção das imagens, inicialização com banco vazio, testes HTTP de integração e verificação de persistência após reiniciar a API e o banco.

O teste de integração passa pelo proxy do frontend e verifica arquivos do site, Swagger, saúde do banco, criação e edição de dados, alocações, cálculo de capacidade, bloqueio de sobrealocação, isolamento entre organizações, auditoria e exclusão.

Para reproduzir o teste com Python 3.11 ou superior instalado e a aplicação em execução:

```powershell
python scripts/test-integration.py
```

Sem instalar Python, no PowerShell:

```powershell
Get-Content -Raw scripts/test-integration.py | docker compose exec -T backend python - --base-url http://frontend
```

Os testes criam organizações exclusivas, removem os cadastros de negócio ao concluir e mantêm os tenants e registros de auditoria. Para avaliação isolada, utilize um ambiente de teste, conforme [o guia Docker](docs/DOCKER-LOCAL.md).

## Problemas comuns

- **Docker não conecta:** abra o Docker Desktop e aguarde iniciar; confirme que está em modo de containers Linux.
- **Porta ocupada:** no PowerShell, execute `$env:IAS_WEB_PORT="5174"` e `$env:IAS_API_PORT="5204"` antes do comando de inicialização. Depois use essas portas nos endereços. Em outros terminais, defina as mesmas variáveis pelo mecanismo correspondente.
- **Site pede tenant:** crie a organização pelo Swagger e informe o ID na engrenagem. O banco de outra instalação não é copiado automaticamente.
- **Falha na inicialização:** consulte `docker compose logs --tail 100` e tente `docker compose up -d --build --wait --wait-timeout 240` novamente.

## Escopo atual

Projeto acadêmico em estágio de MVP. A autenticação usa um fluxo de desenvolvimento, e o tenant pode ser informado pelo cliente. As credenciais do Compose são exclusivas para uso local; site e API ficam vinculados a `127.0.0.1`, e o MySQL não publica porta no computador. Para disponibilizar em produção, é necessário implementar autenticação e autorização completas e configurar segredos adequados.

## Estrutura

```text
Frontend/          Interface e configuração do Nginx
Backend/app/       API e regras de negócio
compose.yaml       Ambiente local completo
scripts/           Testes de integração e utilitários
.github/workflows/ Pipelines de CI
Dockerfile         Imagem alternativa com site e API juntos
```

A documentação em `docs/` contém também registros históricos de arquiteturas anteriores; para instalar a versão Python atual, siga este README e [DOCKER-LOCAL.md](docs/DOCKER-LOCAL.md).

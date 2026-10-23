# IAS — Intelligent Allocation System

## O que é esse projeto?

O IAS é uma ferramenta de organização para **gerentes de projetos (GPs)**. A ideia é reunir em um só lugar as informações que o gerente precisa no dia a dia: quais projetos estão em andamento, quem são os clientes, quem faz parte da equipe, qual é a senioridade de cada pessoa e quem pode assumir uma nova demanda.

Imagine que chegou um projeto e você precisa montar a equipe. No IAS, você consegue consultar os profissionais, ver suas competências e disponibilidade, definir quem vai trabalhar no projeto e quanto do tempo de cada pessoa será dedicado a ele. Isso ajuda a evitar colocar alguém em mais trabalho do que consegue atender e a perceber quando falta gente para uma entrega.

O produto também ajuda a olhar para as próximas semanas: acompanhar a ocupação da equipe, identificar pessoas disponíveis e avaliar necessidades de contratação ou redistribuição. Há ainda visões de custos e margens e simulações para apoiar o planejamento do gerente.

## O que o sistema oferece

- **Pessoas e competências:** listar profissionais, registrar cargo e senioridade e associar habilidades e níveis de conhecimento.
- **Clientes e projetos:** organizar a carteira de clientes e acompanhar os projetos, seus períodos, prioridades e situação.
- **Distribuição do trabalho:** definir quem participa de cada projeto, em qual função, por quanto tempo e com qual dedicação.
- **Disponibilidade e conflitos:** acompanhar a capacidade da equipe e impedir que uma nova alocação ultrapasse o tempo disponível da pessoa.
- **Necessidades e sugestões:** registrar os perfis que um projeto precisa e consultar sugestões de profissionais compatíveis.
- **Planejamento e financeiro:** consultar custos e margens e simular se a equipe consegue atender uma nova demanda.
- **Histórico e organizações:** consultar registros de alterações e manter os dados de cada organização separados.

As telas de **Simulações** e **Financeiro** ficam disponíveis ao ativar **Opções ocultas** no menu de engrenagem do cabeçalho.

> **Primeiro acesso:** depois de subir o Docker, é necessário criar sua organização no Swagger e informar o **Tenant ID** no site. O [tutorial abaixo](#4-primeiro-acesso-criar-a-organização-no-swagger-e-configurar-o-tenant-id) mostra cada etapa.

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

### 4. Primeiro acesso: criar a organização no Swagger e configurar o Tenant ID

O **tenant** representa sua organização dentro do sistema. O **Tenant ID** é o código que identifica essa organização e indica quais dados o site deve carregar. Nesta versão, essa configuração é feita manualmente uma vez por navegador.

O banco é criado automaticamente e começa vazio. Você vai criar sua própria organização; não precisa copiar arquivos `.env` ou usar um ID de outra instalação.

#### 4.1. Abrir o Swagger

1. Deixe o Docker Desktop aberto e execute o comando da etapa 3. Confirme com `docker compose ps` que os três serviços estão **healthy**.
2. Abra uma nova aba no navegador e acesse **[http://localhost:5203/swagger](http://localhost:5203/swagger)**. Esse endereço funciona no computador onde os containers estão rodando.
3. Você verá a página **IAS API**, com uma lista de operações. O Swagger é uma página para experimentar as funções do sistema; vamos usá-lo para criar sua organização.

Se você alterou a porta da API, troque `5203` pela porta escolhida. Se a página não abrir, confira se os containers estão em execução e consulte os logs do backend.

#### 4.2. Criar a organização e copiar o ID

1. Na lista de operações, encontre a linha **`POST /api/v1/tenants`**, com o título **Create Tenant**. Você pode usar `Ctrl+F` e pesquisar `/api/v1/tenants`.
2. Clique nessa linha para expandir a operação. Escolha **POST**, que cria a organização; a operação **GET** serve para consultar uma organização que já existe.
3. Clique no botão **Try it out**.
4. Na caixa **Request body**, substitua o conteúdo pelo exemplo abaixo. Você pode trocar o nome pelo da sua organização:

```json
{"name": "Minha organizacao"}
```

5. Clique no botão **Execute**, logo abaixo da caixa de texto. Não é necessário informar um Tenant ID para criar a primeira organização.
6. Desça até **Responses → Server response**. Confira se o campo **Code** mostra **201**, indicando que a organização foi criada.
7. Em **Response body**, procure o campo **`id`**. A resposta terá um formato parecido com este:

```json
{
  "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "name": "Minha organizacao",
  "isActive": true
}
```

8. Copie **somente o valor de `id` retornado na sua execução**, sem aspas, vírgulas ou o texto `id`. Guarde esse código: você vai usá-lo para abrir a mesma organização novamente. Os `x` acima são apenas uma ilustração e não funcionam no site.

**Atenção:** copie o ID de **Server response → Response body**, que aparece depois de clicar em **Execute**. A área **Example Value** mostra apenas um exemplo de documentação.

Se aparecer **409**, já existe uma organização com esse nome. Use o ID que você guardou ou crie outra com um nome diferente.

#### 4.3. Informar o Tenant ID no site

1. Abra a aplicação em **[http://localhost:5173](http://localhost:5173)**.
2. Clique no ícone de **engrenagem**, no canto superior direito do cabeçalho. O menu se chama **Configuração de desenvolvimento**.
3. No campo **Tenant (X-Tenant-Id)**, cole o ID que você copiou do Swagger.
4. A configuração é salva automaticamente ao preencher o campo; **não existe botão Salvar**. O campo **Ator (opcional)** pode ficar vazio.
5. Feche o menu clicando fora dele. O aviso **“Informe um GUID de tenant válido para carregar os dados.”** deve desaparecer. Se continuar aparecendo, confira se copiou o código completo, sem aspas ou espaços.
6. Comece os cadastros: competências e pessoas; depois clientes e projetos; por fim, necessidades e alocações. Os clientes são cadastrados na tela de projetos.

**As listas vazias no primeiro acesso são esperadas:** a instalação ainda não tem profissionais, clientes ou projetos cadastrados. A indicação **Tenant conectado** confirma o formato do código informado; use sempre o ID real retornado pelo seu Swagger.

Você só precisa criar a organização uma vez. Ao voltar ao site no mesmo navegador, o código fica salvo. Em outro navegador ou computador, informe o mesmo ID para acessar a mesma organização **no mesmo banco**. Se apagar o volume do banco, será necessário criar uma organização novamente.

#### Alternativa: criar a organização pelo PowerShell

Se preferir o terminal, este comando substitui a criação pelo Swagger. Depois, copie o `id` da resposta e siga a etapa **4.3**:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:5203/api/v1/tenants -ContentType 'application/json' -Body '{"name":"Minha organizacao"}'
```

Use um nome diferente para cada organização.

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

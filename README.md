# IAS — Intelligent Allocation System

Plataforma de alocação de pessoas em consultorias: visibilidade operacional, capacidade futura e apoio à decisão comercial.

**Cloud alvo:** AWS (App Runner / ECS / Elastic Beanstalk + RDS MySQL).

## Sobre este projeto

Este projeto nasceu de uma demanda real: fui requisitado para desenvolver um sistema interno de alocação de pessoas para gerentes de projeto em uma consultoria onde trabalhei. O MVP seria apresentado internamente, mas foi descartado — meu desligamento da empresa aconteceu antes da apresentação, e o projeto ficou sem dono. Depois de sair, resgatei o código, removi toda referência à empresa original, refiz partes do meu jeito e publiquei aqui para não deixar o trabalho se perder.

Um detalhe do frontend: o cabeçalho tinha um logo 3D interativo (gira ao passar o mouse, responde a clique), modelado por mim no Blender e integrado via React Three Fiber/Three.js. Essa peça carregava a identidade visual da empresa anterior, então os arquivos de imagem (`.glb` e a imagem de fallback) foram removidos do projeto — mas a funcionalidade em si não foi apagada, só desabilitada: o componente continua em [`Frontend/src/components/InteractiveLogo.tsx`](Frontend/src/components/InteractiveLogo.tsx), funcional e pronto para carregar um novo modelo 3D sem marca de terceiros. O ícone estático "IAS" que aparece hoje no cabeçalho ([`Frontend/src/components/Layout.tsx`](Frontend/src/components/Layout.tsx)) ocupa esse mesmo lugar como placeholder — é o template de onde a versão 3D nova entra quando eu tiver um modelo próprio pronto.

## Documentação

| Arquivo | Conteúdo |
|---------|----------|
| [docs/REQUISITOS_PRODUTO.txt](docs/REQUISITOS_PRODUTO.txt) | O que o produto deve fazer (texto original — referência) |
| [docs/ARQUITETURA.txt](docs/ARQUITETURA.txt) | Stack, domínio, APIs, roadmap técnico |
| [docs/DESENVOLVIMENTO.txt](docs/DESENVOLVIMENTO.txt) | Guia para dev/IA: estado, checklist, convenções |
| [docs/FRONTEND.txt](docs/FRONTEND.txt) | Guia do frontend: stack, padrões, testes, CI |
| [docs/DEPLOY-AWS.txt](docs/DEPLOY-AWS.txt) | Deploy: Docker + RDS MySQL (App Runner / ECS / Beanstalk) |

**Para agentes de IA:** ler `docs/DESENVOLVIMENTO.txt` antes de codar.

## Status atual

- **Fase:** 0 (Fundação) — backend Python em [`Backend/app`](Backend/app)
- **Ambiente:** Python 3.12, Node 22, MySQL 8 (`ias_dev`)
- **Camada 1 (backend):** concluída (CRUD, alocações, views, conflitos, audit log)
- **Frontend:** [`Frontend/`](Frontend/) — React 19 + Vite 6 (dev em http://localhost:5173)
- **Backend Fase 0:** concluída (tenant, user, JWT, CI, RN-003, capacity básico)
- **Roadmap:** [`docs/roadmap/`](docs/roadmap/)
- **Deploy:** Docker na raiz — [`docs/DEPLOY-AWS.txt`](docs/DEPLOY-AWS.txt)

## Estado atual (MVP) — decisões conscientes

Este projeto está em fase de MVP. As simplificações abaixo são intencionais, não lacunas percebidas tarde — cada uma tem um motivo para a fase atual e um caminho já mapeado para evoluir.

| Decisão atual | Por que faz sentido no MVP | Evolução planejada |
|----------------|------------------------------|----------------------|
| Autenticação mock (`POST /auth/dev-token`, sem hash de senha, sem `[Authorize]` nas rotas) | Validar o domínio (alocação, capacidade, matching) antes de fechar autenticação completa | Login real com hash de senha e `[Authorize]` por rota (Fase 0 em andamento) |
| Tenant resolvido pelo header `X-Tenant-Id` | Permite testar multi-tenant sem depender de login pronto | Tenant extraído de claim no JWT — isolamento não depende do cliente informar o header corretamente |
| Testes de integração ainda centrados no domínio | Ciclo de feedback rápido no MVP | Testcontainers + MySQL real, para validar FK, unique index e SQL |
| Detecção de sobrealocação (RN-001) calculada em memória (LINQ sobre as alocações carregadas) | Suficiente na escala de uma demo | Mover para agregação no banco quando o volume de dados justificar |
| Sem dado de exemplo (seed) e sem deploy público ainda | Foco até aqui foi Camada 1 (backend) e Fase 0 | Seed de demonstração + deploy AWS (`docs/DEPLOY-AWS.txt`) |

## Stack resumida

- Backend: [`Backend/`](Backend/) — Python 3.12, FastAPI, SQLAlchemy, MySQL
- Frontend: [`Frontend/`](Frontend/) — React 19, Vite 6, TypeScript, Tailwind, TanStack Query
- Banco local: MySQL 8 (`ias_dev` em localhost:3306)
- Produção: Docker (API + site na mesma imagem) + Amazon RDS MySQL

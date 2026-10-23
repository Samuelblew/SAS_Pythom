# Validação da entrega Docker

## Como reproduzir

Siga o [teste isolado](DOCKER-LOCAL.md#teste-isolado-com-banco-novo) para executar
as verificações com um volume novo. A CI reproduz o processo no GitHub Actions.

## Cobertura

- Frontend: 22 testes em 7 arquivos; lint e compilação TypeScript/Vite.
- Backend: compilação dos módulos Python.
- Integração: site, assets, rotas SPA, Swagger, saúde do MySQL e exigência de tenant.
- Dados: tenant, cliente, competência, profissional, vínculo de competência,
  projeto, alocação, edição, leitura e exclusão lógica.
- Negócio: alocação de 60% em uma semana de 40 horas deixa 16 horas disponíveis;
  mais 50% no mesmo período retorna HTTP 409; excluir a alocação libera a capacidade.
- Isolamento: outra organização não pode consultar o profissional criado.
- Auditoria: operações geram registros consultáveis.
- Persistência: organização criada antes do reinício continua disponível depois.

## Correção identificada pelos testes

Requisições sequenciais rápidas revelaram que o commit era executado depois
da resposta HTTP. Um cadastro podia retornar 201 e uma leitura imediata retornar
404. As dependências de banco agora usam `scope="function"`, com FastAPI 0.121.1,
para concluir commit/rollback antes de enviar a resposta. Os testes fazem leituras
imediatas após a criação, sem pausas ou tentativas que ocultem essa falha.

Referência: [ciclo das dependências FastAPI](https://fastapi.tiangolo.com/advanced/advanced-dependencies/).

## Limites

Os testes HTTP passam pelo Nginx e pela API real com MySQL real; não automatizam
cliques no navegador nem avaliam carga, segurança de produção ou todos os cenários
de negócio. Lint pode emitir avisos de Fast Refresh; eles não são erros.
O build Docker instala pelo lockfile sem executar auditoria de vulnerabilidades;
essa auditoria não é uma condição de aprovação desta pipeline.

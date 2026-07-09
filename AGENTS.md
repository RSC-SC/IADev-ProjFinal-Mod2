# Fluxo de Desenvolvimento (Instruções para o Agente IA)

Sempre que for realizada uma alteração no código deste projeto, o seguinte fluxo DEVE ser seguido:

## Fluxo Obrigatório

1. **Criar Issue no GitHub**
   - Descrever a tarefa com título e descrição claros
   - Adicionar labels se aplicável

2. **Criar branch a partir de `dev`**
   - Nome padrão: `feature/<descricao-curta>` ou `fix/<descricao-curta>`

3. **Implementar a alteração**
   - Fazer checkout na branch criada
   - Implementar o código conforme definido na Issue

4. **Commit**
   - Usar mensagens semânticas claras (ex: `feat:`, `fix:`, `docs:`, `refactor:`)

5. **Criar Pull Request para `dev`**
   - PR deve referenciar a Issue (ex: `Closes #1`)
   - Descrever as mudanças realizadas

6. **Documentar na Issue**
   - Atualizar a Issue com o link do PR e status da implementação

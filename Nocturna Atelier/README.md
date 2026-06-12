# Nocturna Atelier

Loja dark premium para joias autorais, com identidade visual própria, imagens geradas, animações suaves, experiência responsiva e backend funcional em Python.

## Sobre o projeto

A **Nocturna Atelier** é uma vitrine de luxo para joias em ouro antigo, ônix, diamantes negros e esmeraldas. O layout foi pensado para transmitir sofisticação, exclusividade e alto contraste visual, usando uma paleta escura com detalhes em dourado.

## Recursos

- Nome e marca próprios: Nocturna Atelier
- Logo em SVG criado para o projeto
- Favicon personalizado
- Imagens locais otimizadas para hero e produtos
- Cards de produto com hover e zoom suave
- Animações no scroll
- API de produtos, sacola, newsletter e pedidos
- Carrinho funcional com persistência local por sessão
- Checkout com criação de pedido
- Cadastro de e-mail para lançamentos privados
- Layout responsivo para desktop e mobile
- Sem dependências externas de ícones ou fontes

## Estrutura

```text
src/
  assets/
    favicon.svg
    nocturna-hero.jpg
    product-bracelet.jpg
    product-earrings.jpg
    product-necklace.jpg
    product-ring.jpg
  index.html
  script.js
  style.css
data/
  products.json
  store.json
server.py
```

## Como executar

Use Python 3 e execute:

```bash
py server.py
```

Depois acesse:

```text
http://localhost:3000
```

O backend expõe rotas em `/api/products`, `/api/cart`, `/api/newsletter` e `/api/orders`.

## Autor e contato

Desenvolvido por **Wesley Cruz**.

- Usuário: wesley.cruz
- Projeto: Nocturna Atelier
- GitHub: WessYu
- Email: wess.c@proton.me


## Licenca

Este projeto está licenciado sob a licença MIT. Veja o arquivo [LICENSE.txt](LICENSE.txt).

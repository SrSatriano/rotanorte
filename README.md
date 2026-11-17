# 🧭 RotaNorte – vagas reais com visto para EUA e Canadá

[![CI](https://github.com/SrSatriano/rotanorte/actions/workflows/ci.yml/badge.svg)](https://github.com/SrSatriano/rotanorte/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![dependências](https://img.shields.io/badge/depend%C3%AAncias-s%C3%B3_biblioteca_padr%C3%A3o-22c55e)

Sistema pessoal que roda no seu computador e:

1. **Busca vagas em fontes oficiais** (governo dos EUA e do Canadá) de empregadores que contratam estrangeiros.
2. **Dá uma nota de 0 a 100** para cada vaga, de acordo com o seu perfil e a sua família.
3. **Gera currículo e carta em inglês** para cada vaga.
4. **Explica os caminhos de visto** possíveis e monta um **plano de ação**.
5. **Detecta golpes** em propostas que você receber.
6. **Acompanha suas candidaturas.**

## Como usar (Windows)

1. Instale o **Python** (grátis): https://www.python.org/downloads/windows/
   Na primeira tela da instalação, **marque "Add python.exe to PATH"**.
2. Dê dois cliques em **`INICIAR.bat`**. O RotaNorte abre numa **janela própria, como um
   aplicativo** (usa o Edge ou o Chrome em modo app, sem abas). Para encerrar, é só fechar essa janela.
   Dica: rode **`CRIAR_ATALHO.bat`** uma vez para ter o ícone "RotaNorte" na Área de Trabalho.
3. Vá em **Perfil** e complete seus dados (inglês, anos de cada experiência, nome, contato).
4. Na aba **Início**, clique em **Buscar vagas agora**. A primeira busca leva alguns minutos.

Outros arquivos:

| Arquivo | Para que serve |
|---|---|
| `AGENDAR_BUSCA_DIARIA.bat` | Faz o Windows buscar vagas sozinho todo dia às 8h |
| `COLETAR.bat` | Faz uma busca sem abrir o painel (o log fica em `dados/coleta.log`) |
| `DIAGNOSTICO.bat` | Testa se o computador consegue acessar as fontes oficiais |
| `CRIAR_ATALHO.bat` | Cria o atalho "RotaNorte" na Área de Trabalho |
| `ABRIR_COM_LOG.bat` | Abre mostrando as mensagens (use se algo não abrir) |

## De onde vêm as vagas

| Fonte | O que é | Por que é confiável |
|---|---|---|
| **SeasonalJobs.dol.gov** (EUA) | Feed oficial diário do Departamento do Trabalho com pedidos de visto **H-2B** | Toda vaga é de empregador que pediu ao governo para contratar estrangeiros |
| **Job Bank** (Canadá) | Site oficial de empregos do governo canadense | O sistema abre cada anúncio e só marca "aceita estrangeiro" se o empregador aceitar candidatos "with or without a valid Canadian work permit" |
| **Lista de LMIA positivo** (Canadá) | Lista trimestral oficial de empresas aprovadas para contratar estrangeiros | Publicada pelo governo no Portal de Dados Abertos |
| **Empregadores designados AIP** (Canadá Atlântico) | Listas oficiais de Terra Nova e Labrador e Nova Escócia | Oferta desses empregadores pode levar direto à residência permanente |
| **PERM / green card** (EUA) | Arquivo trimestral oficial do Departamento do Trabalho | Empresas que já tiveram green card de estrangeiro aprovado na sua área |
| Adzuna (opcional) | Agregador privado | Só ganha selo verde se o texto falar em patrocínio de visto |

O RotaNorte **não envia candidaturas sozinho**: cada empregador recebe de um jeito
e envio em massa queima seu nome. Ele prepara tudo para você enviar em poucos minutos.

## Novidades da versão 1.2

- **Currículo em PDF** com um clique (usa o Edge/Chrome do próprio PC). Os arquivos ficam em `dados/documentos`.
- **Avisos no celular pelo Telegram**: configure em *Meu perfil → Avisos no celular*.
- **Aba Empresas** com três listas: LMIA aprovado, AIP (residência permanente) e green card (PERM).
- `INSTALAR_EXTRAS.bat` instala o leitor de PDF (pypdf), usado para a lista da Nova Escócia.

## Regras de imigração

As regras foram conferidas em **10/11/2026** e ficam no arquivo `app/caminhos.py`.
Elas mudam com frequência – confira sempre os links oficiais da aba **Caminhos de visto**.
Isto é informação, **não aconselhamento jurídico**.

## Passar para outra pessoa

1. Copie a pasta inteira.
2. Na cópia, apague a pasta `dados` e o arquivo `config/perfil.json`.
3. A pessoa abre `INICIAR.bat` e preenche o próprio perfil.

## Privacidade

Tudo fica no seu computador (`config/` e `dados/`). O painel só aceita acessos do próprio PC.
O sistema só acessa sites do governo (e o Adzuna, se você ativar).

## Problemas comuns

- **"Python não encontrado"**: reinstale o Python marcando "Add python.exe to PATH".
- **Busca falhou**: rode `DIAGNOSTICO.bat`. Sites do governo às vezes ficam fora do ar à noite ou no fim de semana; tente mais tarde. Antivírus/firewall corporativo podem bloquear.
- **Porta ocupada**: não precisa fazer nada. Se a porta 8765 estiver em uso por outro programa, o
  RotaNorte procura sozinho a próxima livre (8766, 8767…). Se ele já estiver aberto, só traz a janela de volta.
- **Não abriu nada**: use `ABRIR_COM_LOG.bat` para ver a mensagem de erro (ou veja `dados/painel.log`).
- **Testes (para quem programa)**: `py -m unittest discover -s tests`

Feito com Python puro (sem instalar bibliotecas extras).

## Autor

Matheus Rodrigues Satriano — [github.com/SrSatriano](https://github.com/SrSatriano)

"""Portuguese (Brazil) translations: English text in the code -> text on screen. One section per screen.

Placeholders like {n} or {title} must be kept. tests/test_i18n.py checks that every tr()/trn() text in
the code has an entry here.
"""
PT = {}

# ------------------------------------------------------------------ data values (stored in English)
PT.update({
    # habit answers
    "Excellent": "Excelente", "Ok": "Ok", "A Little": "Um pouco", "Skipped": "Pulei",
    "Resisted": "Resisti", "Slipped": "Escorreguei", "Relapsed": "Recaí", "Rest": "Descanso",
    "Exc": "Exc", "Little": "Pouco", "Skip": "Pulei",
    # categories
    "Health": "Saúde", "Study": "Estudos", "Routine": "Rotina", "Vice / Avoid": "Vício / Evitar",
    # quests
    "Main": "Principal", "Side": "Secundária", "Epic": "Épica",
    "Easy": "Fácil", "Normal": "Normal", "Hard": "Difícil",
    "Active": "Em andamento", "On hold": "Em pausa", "Complete": "Concluída",
    "none": "não repete", "weekly": "semanal", "monthly": "mensal",
    # study stages
    "Not started": "Não iniciado", "Studying": "Estudando", "Reviewing": "Revisando", "Mastered": "Dominado",
    # ranks
    "Novice": "Novato", "Apprentice": "Aprendiz", "Disciplined": "Disciplinado", "Elite": "Elite",
    "Master": "Mestre", "Centurion": "Centurião",
})

# ------------------------------------------------------------------ common words
PT.update({
    "Save": "Salvar", "Cancel": "Cancelar", "Delete": "Excluir", "Close": "Fechar", "Edit": "Editar",
    "Add": "Adicionar", "Remove": "Remover", "Today": "Hoje", "Yesterday": "Ontem", "Tomorrow": "Amanhã",
    "today": "hoje", "yesterday": "ontem", "tomorrow": "amanhã", "Back": "Voltar", "Next": "Próximo",
    "Previous": "Anterior", "Yes": "Sim", "No": "Não", "Done": "Feito", "Apply": "Aplicar", "Retry": "Tentar de novo",
})

# ------------------------------------------------------------------ main window, tray, alarms
PT.update({
    "Schedule": "Hábitos", "Graphs": "Gráficos", "Quests": "Missões", "Diary": "Diário",
    "Wallpaper": "Papel de parede", "Calendar": "Calendário", "Documents": "Documentos", "Options": "Opções",
    "Workout / Gym": "Treino / Academia", "Stretching": "Alongamento", "Healthy Diet": "Alimentação saudável",
    "1h Study / Course": "1h de estudo / curso", "Walk with Dog": "Passear com o cachorro",
    "Quit Application Completely": "Fechar o aplicativo completamente",
    "Open Tracker": "Abrir o Tracker", "Refresh Wallpaper": "Atualizar papel de parede", "Exit": "Sair",
    "Marking as completed awards +10 XP towards your Discipline Level!":
        "Marcar como feito dá +10 XP para o seu nível de disciplina!",
    "Dismiss": "Dispensar", "I Did It! (+10 XP)": "Eu fiz! (+10 XP)",
    "'{title}' expires today. Renew it when you can.": "'{title}' vence hoje. Renove quando puder.",
    "'{title}' expired on {date}. Renew it when you can.": "'{title}' venceu em {date}. Renove quando puder.",
    "'{title}' expires in {n} days ({date}).": "'{title}' vence em {n} dias ({date}).",
    "'{title}' expires on {date} — time to plan the renewal.":
        "'{title}' vence em {date} — hora de planejar a renovação.",
    "{n} habit still unmarked today.": "{n} hábito ainda sem marcar hoje.",
    "{n} habits still unmarked today.": "{n} hábitos ainda sem marcar hoje.",
    "Daily check-in": "Check-in do dia", "Document reminder": "Lembrete de documento",
    "today (all day)": "hoje (o dia todo)", "tomorrow (all day)": "amanhã (o dia todo)",
    "at {time} (in {n} min)": "às {time} (em {n} min)", "at {time}": "às {time}",
    "Upcoming appointment": "Próximo compromisso", "🚨 Event Starting NOW!": "🚨 Evento começando AGORA!",
    "'{title}' starts now ({time})!": "'{title}' começa agora ({time})!",
})

# ------------------------------------------------------------------ graphs + analytics
PT.update({
    "Last 7 days": "Últimos 7 dias", "Last 30 days": "Últimos 30 dias", "Last 12 weeks": "Últimas 12 semanas",
    "Last 12 months": "Últimos 12 meses",
    "previous 7 days": "período anterior", "previous 30 days": "período anterior",
    "previous 12 weeks": "período anterior", "previous 12 months": "período anterior",
    "{n} days": "{n} dias", ", {n} rest": ", {n} de descanso",
    "Score": "Nota", "Daily score": "Nota do dia", "no entry": "sem registro", "rest": "descanso",
    "No habit entries in this period": "Nenhum hábito registrado neste período",
    "Mark your habits in the Schedule and the charts will fill in.":
        "Marque seus hábitos na aba Hábitos e os gráficos vão se preencher.",
    "no data for {period}": "sem dados no {period}", "same as {period}": "igual ao {period}",
    "{value} vs {period}": "{value} vs {period}",
    "{n} day": "{n} dia",
    "Average score": "Nota média", "Mean of the daily averages": "Média das notas diárias",
    "Days logged": "Dias registrados", " · {n} rest": " · {n} de descanso",
    "XP earned": "XP ganho", "Habits, quests, studies, reviews and events": "Hábitos, missões, estudos, revisões e eventos",
    "Best streak": "Maior sequência",
    "Consecutive days with an average of {score} or more": "Dias seguidos com média {score} ou mais",
    "Study time": "Tempo de estudo", "Time logged in study journal entries": "Tempo registrado no diário de estudos",
    "Set up your Gemini key (Options → AI) to get a short summary of each week here.":
        "Configure sua chave do Gemini (Opções → IA) para ver aqui um resumo curto de cada semana.",
    "Gemini is reading your week…": "O Gemini está lendo a sua semana…",
    "Write it again": "Escrever de novo", "No summary yet for this week.": "Ainda não há resumo desta semana.",
    "Write this week's summary": "Escrever o resumo da semana", "This week": "Esta semana",
    "Average per week": "Média por semana", "Average per day": "Média por dia",
    " • latest {latest} • period average {avg} • dashed line = goal {goal}":
        " • última {latest} • média do período {avg} • linha tracejada = meta {goal}",
    "Daily score trend": "Evolução da nota diária",
    "{label}: mood {value}": "{label}: humor {value}",
    "Mood on days ≥ {score}": "Humor nos dias ≥ {score}", "no such days yet": "nenhum dia assim ainda",
    "Mood on other days": "Humor nos outros dias",
    "From the Diary • average per week • {n} week with a mood": "Do Diário • média por semana • {n} semana com humor",
    "From the Diary • average per week • {n} weeks with a mood": "Do Diário • média por semana • {n} semanas com humor",
    "From the Diary • {n} day with a mood": "Do Diário • {n} dia com humor",
    "From the Diary • {n} days with a mood": "Do Diário • {n} dias com humor",
    "Mood": "Humor",
    "week of {date}": "semana de {date}", "{n} rest day": "{n} dia de descanso", "{n} rest days": "{n} dias de descanso",
    "One cell per habit per week (average). Vices count as resisted = 10.":
        "Uma célula por hábito por semana (média). Vícios contam resistido = 10.",
    "One cell per habit per day. Vices count as resisted = 10.":
        "Uma célula por hábito por dia. Vícios contam resistido = 10.",
    "Habit heatmap": "Mapa de calor dos hábitos", " (vice)": " (vício)",
    "{name}: average {avg} on {days} of {total} days": "{name}: média {avg} em {days} de {total} dias",
    " ({n} rest)": " ({n} de descanso)", "{days}/{total} days": "{days}/{total} dias", " • {n} rest": " • {n} de descanso",
    "Average score, strongest first; the bottom ones are where a little attention pays off most.":
        "Nota média, do mais forte ao mais fraco; os de baixo são onde um pouco de atenção rende mais.",
    "Habit ranking": "Ranking dos hábitos",
    "{day}: {avg} ({n} days)": "{day}: {avg} ({n} dias)", "{day}: no entries": "{day}: sem registros",
    "Average daily score per weekday": "Nota média por dia da semana",
    " • strongest {best} ({best_avg}) • lightest {worst} ({worst_avg})":
        " • mais forte {best} ({best_avg}) • mais leve {worst} ({worst_avg})",
    "Weekday pattern": "Padrão da semana",
    "{date}: rest day": "{date}: dia de descanso", "{date}: no entries": "{date}: sem registros",
    "Year map": "Mapa do ano",
    "Last 12 months, one square per day • {n} days logged": "Últimos 12 meses, um quadrado por dia • {n} dias registrados",
    "Week of {date}: {xp} XP": "Semana de {date}: {xp} XP",
    "XP gained": "XP ganho", "net loss (low habit days)": "perda líquida (dias fracos de hábitos)",
    "XP per week": "XP por semana",
    "Net XP from every source • {xp} XP in these weeks": "XP líquido de todas as fontes • {xp} XP nestas semanas",
    "Week of {date}: {value}": "Semana de {date}: {value}",
    "Week of {date}: {n} review(s)": "Semana de {date}: {n} revisão(ões)",
    "Week of {date}: {n} quest(s)": "Semana de {date}: {n} missão(ões)",
    "Study reviews done": "Revisões de estudo feitas", "Quests completed": "Missões concluídas",
    "Study time per week": "Tempo de estudo por semana",
    "{time} logged in your study journal": "{time} registrados no seu diário de estudos",
    "Reviews & quests per week": "Revisões e missões por semana",
    "{reviews} review(s) • {quests} quest(s) completed": "{reviews} revisão(ões) • {quests} missão(ões) concluída(s)",
})

# ------------------------------------------------------------------ schedule (habits)
PT.update({
    "{n} Day Streak": "{n} dia seguido", "{n} Days Streak": "{n} dias seguidos",
    "Level {level} / 100 • {rank}": "Nível {level} / 100 • {rank}",
    "MAX LEVEL REACHED! (1,000 XP)": "NÍVEL MÁXIMO ALCANÇADO! (1.000 XP)",
    "{xp} / 10 XP to Lvl {next} (Total: {total} / 1000)": "{xp} / 10 XP para o nível {next} (Total: {total} / 1000)",
    "Exported to Desktop!": "Exportado para a Área de Trabalho!",
    "Name": "Nome", "Category": "Categoria", "Edit habit": "Editar hábito",
    "Vice / bad habit (inverted scoring)": "Vício / mau hábito (pontuação invertida)",
    "Positive habit": "Hábito positivo", "Delete habit?": "Excluir hábito?",
    "'{name}' will be removed from the grid, charts and daily XP.":
        "'{name}' será removido da grade, dos gráficos e do XP diário.",
    "Remind me to do my check-in": "Me lembrar de fazer o check-in", "At": "Às",
    "Nightly check-in reminder": "Lembrete noturno de check-in",
    "A tray notification appears at this time only if some of today's habits are still unmarked. The tracker also opens on this tab.":
        "Uma notificação aparece na bandeja neste horário só se algum hábito de hoje ainda estiver sem marcar. "
        "O Tracker também abre nesta aba.",
    "Quick-Fill Today": "Preencher hoje", "Marks every unmarked habit today as Ok / Resisted":
        "Marca todo hábito ainda sem resposta hoje como Ok / Resisti",
    "Export CSV": "Exportar CSV",
    "Today {marked}/{total} marked": "Hoje {marked}/{total} marcados",
    "• Editing a past week (XP updates accordingly)": "• Editando uma semana passada (o XP se ajusta)",
    "Previous week": "Semana anterior", "Week {week} ({year})": "Semana {week} ({year})", "Next week": "Próxima semana",
    "Keys: 1-4 mark • R rest • N note • 0 clear • arrows move":
        "Teclas: 1-4 marcam • R descanso • N nota • 0 limpa • setas movem",
    "Check-in reminder at {time}": "Lembrete de check-in às {time}", "Check-in reminder off": "Lembrete de check-in desligado",
    "Activity & Category": "Atividade e categoria", " (Today)": " (Hoje)",
    "Move Up": "Subir", "Move Down": "Descer", "Delete activity": "Excluir atividade",
    "{status} (+{score}) • key {key}": "{status} (+{score}) • tecla {key}",
    " • click again to clear": " • clique de novo para limpar",
    "Rest day — doesn't count in any score • click again to clear":
        "Dia de descanso — não conta em nenhuma nota • clique de novo para limpar",
    "Rest day: this habit doesn't apply today; no score impact • key R • {left} of {limit} left this week":
        "Dia de descanso: este hábito não se aplica hoje; não afeta a nota • tecla R • restam {left} de {limit} nesta semana",
    "No rest days left this week ({n} used)": "Sem dias de descanso nesta semana ({n} usados)",
    "Edit your diary note • key N": "Editar sua nota do diário • tecla N",
    "Write a diary note about it • key N": "Escrever uma nota no diário • tecla N",
    "Rest  (no score)": "Descanso  (sem nota)", "Clear": "Limpar",
    "Edit diary note…": "Editar nota do diário…", "Write a diary note…": "Escrever nota no diário…",
    "rest day": "dia de descanso", "not marked": "sem marcar", " • has a diary note": " • tem nota no diário",
    "New activity name...": "Nome da nova atividade...", "Vice / Bad Habit": "Vício / mau hábito",
    "Add Activity": "Adicionar atividade", "Daily Score (0-10)": "Nota do dia (0-10)",
})

# ------------------------------------------------------------------ quests
PT.update({
    "One-time": "Uma vez", "Every week": "Toda semana", "Every month": "Todo mês",
    "No active quests. Add one above, or let ✨ plan one with you!":
        "Nenhuma missão em andamento. Crie uma acima ou deixe o ✨ planejar uma com você!",
    "Nothing on hold.": "Nada em pausa.",
    "Completed quests will be celebrated here.": "As missões concluídas serão celebradas aqui.",
    "What do you want to achieve?": "O que você quer conquistar?",
    "Context (optional): where you are now, constraints, what you know":
        "Contexto (opcional): onde você está agora, limitações, o que você já sabe",
    "Plan with AI": "Planejar com IA", "Suggest steps": "Sugerir passos", "Create quest": "Criar missão",
    "Add selected steps": "Adicionar passos selecionados",
    "Gemini is planning your quest…": "O Gemini está planejando sua missão…",
    "Completed {date} • +{xp} XP": "Concluída {date} • +{xp} XP", "STEPS ({done}/{total})": "PASSOS ({done}/{total})",
    "Step done! +{xp} XP": "Passo feito! +{xp} XP", "Edit target": "Editar meta", "TARGET": "META",
    "QUEST LOG ({n})": "REGISTRO DA MISSÃO ({n})", "DESCRIPTION & NOTES": "DESCRIÇÃO E NOTAS",
    "Quest title": "Título da missão", "Type": "Tipo", "Difficulty": "Dificuldade", "Repeats": "Repete",
    "Description": "Descrição",
    "First step (becomes your 'next step' bookmark)": "Primeiro passo (vira o seu marcador de 'próximo passo')",
    "Track a numeric target": "Acompanhar uma meta numérica", "Unit": "Unidade", "Start": "Início", "Target": "Meta",
    "Steps (untick or edit before saving):": "Passos (desmarque ou edite antes de salvar):",
    "Describe your goal first.": "Descreva seu objetivo primeiro.", "Plan again": "Planejar de novo",
    "The quest needs a title.": "A missão precisa de um título.", "New quest…": "Nova missão…", "Quest": "Missão",
    "Repeatable quests can be completed once per week/month":
        "Missões repetíveis podem ser concluídas uma vez por semana/mês",
    "{done}/{total} steps": "{done}/{total} passos", "{current} of {target} {unit}": "{current} de {target} {unit}",
    "completed {n} time": "concluída {n} vez", "completed {n} times": "concluída {n} vezes",
    "+{xp} XP — nice! See you next week.": "+{xp} XP — boa! Até semana que vem.",
    "+{xp} XP — nice! See you next month.": "+{xp} XP — boa! Até o mês que vem.",
    "What's the next small step?": "Qual é o próximo passo pequeno?", "Add a step…": "Adicionar um passo…",
    "Unit (kg, books, km, R$…)": "Unidade (kg, livros, km, R$…)", "Start value": "Valor inicial",
    "Target value": "Valor da meta",
    "Fill the unit and two different numbers.": "Preencha a unidade e dois números diferentes.",
    "What did you do? Progress, ideas, blockers…": "O que você fez? Progresso, ideias, bloqueios…",
    "Next step (updates the bookmark)": "Próximo passo (atualiza o marcador)",
    "Write something first.": "Escreva algo primeiro.",
    "Logged! +{xp} XP": "Registrado! +{xp} XP", "Entry": "Registro", "Value ({unit})": "Valor ({unit})", "Date": "Data",
    "Check the date (DD/MM/YYYY), the value, and that the entry isn't empty.":
        "Confira a data (DD/MM/AAAA), o valor e se o registro não está vazio.",
    "Why this quest matters, links, references, ideas…": "Por que esta missão importa, links, referências, ideias…",
    "Suggested extra steps (untick the ones you don't want):": "Passos extras sugeridos (desmarque os que não quiser):",
    "Fill unit, start and target (numbers) or untick the target.":
        "Preencha unidade, início e meta (números) ou desmarque a meta.",
    "Put on hold": "Pausar", "Move quest up": "Subir missão", "Move quest down": "Descer missão",
    "Delete quest": "Excluir missão", "Complete quest": "Concluir missão",
    "All steps done — turn it in!": "Todos os passos feitos — entregue!",
    "No steps yet. Break the quest into small actions — or let ✨ suggest some.":
        "Ainda sem passos. Divida a missão em ações pequenas — ou deixe o ✨ sugerir algumas.",
    "Log your first value below to start the chart.": "Registre seu primeiro valor abaixo para começar o gráfico.",
    "New value ({unit})": "Novo valor ({unit})", "Note (optional)": "Nota (opcional)", "Type a number.": "Digite um número.",
    "Logged {value} {unit}": "Registrado {value} {unit}", "Remove target": "Remover meta",
    "Logged (write {n}+ characters to earn XP).": "Registrado (escreva {n}+ caracteres para ganhar XP).",
    "Logged (today's log XP for this quest already earned).": "Registrado (o XP de hoje desta missão já foi ganho).",
    "No entries yet — a line per session is enough.": "Ainda sem registros — uma linha por sessão já basta.",
    "Edit entry": "Editar registro", "Delete entry": "Excluir registro",
    "AI quest planner": "Planejador de missões com IA",
    "Gemini had no extra steps to add.": "O Gemini não tinha passos extras para sugerir.",
    "Also track a target: {start} → {target} {unit}": "Acompanhar também uma meta: {start} → {target} {unit}",
    "Quest Log": "Diário de missões", "Done this week ✓ • back {date}": "Feita nesta semana ✓ • volta {date}",
    "Done this month ✓ • back {date}": "Feita neste mês ✓ • volta {date}", "{repeat} • ready": "{repeat} • pronta",
    "Resume": "Retomar", "Completed {date} • +{xp} XP earned": "Concluída {date} • +{xp} XP ganhos", "Reopen": "Reabrir",
    "On hold — resume it to complete.": "Em pausa — retome para concluir.",
    "You can complete it whenever you feel it's done.": "Você pode concluir quando sentir que terminou.",
    "'{title}' joins your Hall of Fame. +{xp} XP": "'{title}' entrou no seu Hall da Fama. +{xp} XP",
    "Steps reset every Monday.": "Os passos reiniciam toda segunda-feira.",
    "Steps reset on the 1st of each month.": "Os passos reiniciam no dia 1º de cada mês.",
    "Rename step": "Renomear passo",
    "Is progress a number? (kg, books, km, money…) Track it here.":
        "O progresso é um número? (kg, livros, km, dinheiro…) Acompanhe aqui.",
    "Measurable target": "Meta mensurável", "Edit log entry": "Editar registro",
    "The planner uses the same Gemini key as the AI study reviews (Options → AI).":
        "O planejador usa a mesma chave do Gemini das revisões de estudo (Opções → IA).",
    "Open AI settings": "Abrir configurações de IA", "Plan a new quest with AI": "Planejar uma nova missão com IA",
    "Add quest": "Adicionar missão", "Untitled": "Sem título", "Delete quest?": "Excluir missão?",
    "'{title}', its steps and its log will be removed.": "'{title}', seus passos e seu registro serão removidos.",
    "Undo": "Desfazer", "Complete this week": "Concluir nesta semana", "Complete this month": "Concluir neste mês",
    "Awesome": "Demais!", "START": "INÍCIO", "NOW": "AGORA", "Log value": "Registrar valor",
    "Log (+{xp} XP)": "Registrar (+{xp} XP)",
    "Delete log entry?": "Excluir registro?", "The entry from {date} will be removed.": "O registro de {date} será removido.",
    "More steps for '{title}'": "Mais passos para '{title}'",
    "This week: {n} quest done • +{xp} XP from quests": "Esta semana: {n} missão concluída • +{xp} XP de missões",
    "This week: {n} quests done • +{xp} XP from quests": "Esta semana: {n} missões concluídas • +{xp} XP de missões",
    "Done this week! Available again {date}.": "Feita nesta semana! Disponível de novo {date}.",
    "Done this month! Available again {date}.": "Feita neste mês! Disponível de novo {date}.",
    "Quest complete!": "Missão concluída!", "Rename": "Renomear", "Move step up": "Subir passo",
    "Move step down": "Descer passo", "Delete step": "Excluir passo",
    "Add a measurable target": "Adicionar uma meta mensurável",
    "No deadlines: Gemini is told to order steps, never to schedule them.":
        "Sem prazos: o Gemini é instruído a ordenar os passos, nunca a agendá-los.",
    "Active {n}": "Em andamento {n}", "On hold {n}": "Em pausa {n}", "Hall of Fame {n}": "Hall da Fama {n}",
    "Start a quest on the left — or press ✨ and plan one with Gemini.":
        "Comece uma missão à esquerda — ou aperte ✨ e planeje uma com o Gemini.",
    "Reopen quest?": "Reabrir missão?",
    "It leaves the Hall of Fame and its +{xp} XP is removed until you complete it again.":
        "Ela sai do Hall da Fama e seus +{xp} XP são removidos até você concluí-la de novo.",
    "NEXT STEP": "PRÓXIMO PASSO", "Add step": "Adicionar passo",
    "Works both ways: 82 → 77 kg (going down) or 0 → 12 books (going up). Logged values keep their history.":
        "Funciona nos dois sentidos: 82 → 77 kg (descendo) ou 0 → 12 livros (subindo). "
        "Os valores registrados guardam o histórico.",
})

# ------------------------------------------------------------------ study
PT.update({
    # data shown through tr() (sources, filters, stages focus, verdicts, wrap-up templates)
    "Documentation / Book": "Documentação / Livro", "Self-Study": "Autodidata",
    "No chapters in progress.\nAdd one above!": "Nenhum capítulo em andamento.\nAdicione um acima!",
    "Nothing mastered yet — keep going!": "Nada dominado ainda — continue!",
    "No reviews due today. 🎉": "Nenhuma revisão para hoje. 🎉",
    "No chapters here yet.\nAdd one above!": "Ainda não há capítulos.\nAdicione um acima!",
    "recall": "lembrar", "application": "aplicação", "scenarios & edge cases": "cenários e casos-limite",
    "synthesis — teach it back": "síntese — explique de volta",
    "Correct": "Correto", "Partially correct": "Parcialmente correto", "Not quite": "Ainda não",
    "MODEL ANSWER": "RESPOSTA MODELO", "WHAT THE LESSON WAS ABOUT": "SOBRE O QUE FOI A AULA",
    "KEY CONCEPTS": "CONCEITOS-CHAVE", "GAPS IN YOUR NOTES": "LACUNAS NAS SUAS NOTAS",
    "YOUR FLASHCARDS": "SEUS FLASHCARDS", "ELI5 SUMMARY": "RESUMO ELI5",
    "• What is it?\n->\n\n• What problem does it solve?\n->\n\n• Real-world analogy / Simple metaphor:\n-> ":
        "• O que é?\n->\n\n• Que problema resolve?\n->\n\n• Analogia do mundo real / metáfora simples:\n-> ",
    "# 2. Minimal Proof of Work Example\n# (Write from scratch from memory, not copied from the video)\n\n"
    "def proof_of_work():\n    pass\n":
        "# 2. Exemplo mínimo de prova de trabalho\n# (Escreva do zero, de memória, sem copiar do vídeo)\n\n"
        "def proof_of_work():\n    pass\n",
    "• If I remove or change [X], what error happens?\n->\n\n• When should I NOT use this?\n->\n\n"
    "• Common edge cases & pitfalls:\n-> ":
        "• Se eu remover ou mudar [X], que erro acontece?\n->\n\n• Quando NÃO devo usar isto?\n->\n\n"
        "• Casos-limite e armadilhas comuns:\n-> ",
    "Q1:\nA1:\n\nQ2:\nA2: ": "Q1:\nA1:\n\nQ2:\nA2: ",
    "1. The ELI5 Summary (explain it simply, no jargon)": "1. O resumo ELI5 (explique de forma simples, sem jargão)",
    "2. The Toy Sandbox (proof-of-work code example)": "2. A caixa de areia (exemplo de código como prova de trabalho)",
    "3. The Break-It Test (edge cases & common failures)": "3. O teste de quebrar (casos-limite e falhas comuns)",
    "4. Active Recall Flashcards (Q1: … / A1: …) — used in your reviews":
        "4. Flashcards de lembrança ativa (Q1: … / A1: …) — usados nas suas revisões",
    # screens
    "In {n} day": "Em {n} dia", "In {n} days": "Em {n} dias", "Check with AI": "Corrigir com IA",
    "Set up your Gemini API key in AI settings": "Configure sua chave da API do Gemini nas configurações de IA",
    "Struggled — repeated": "Com dificuldade — repetida", "Overdue ({n}d)": "Atrasada ({n}d)", "Due today": "Para hoje",
    "Your answer…": "Sua resposta…",
    "Try to answer each question from memory, then reveal the answers.":
        "Tente responder cada pergunta de memória e depois revele as respostas.",
    "Gemini API key": "Chave da API do Gemini",
    "Paste a key to save or replace it (the saved key is never shown)":
        "Cole uma chave para salvar ou substituir (a chave salva nunca é mostrada)",
    "Preferred model (optional)": "Modelo preferido (opcional)",
    "e.g. gemini-2.5-flash — empty = automatic": "ex.: gemini-2.5-flash — vazio = automático",
    "Generate an AI review pack automatically when I master a chapter":
        "Gerar um pacote de revisão com IA automaticamente quando eu dominar um capítulo",
    "Saved.": "Salvo.", "Key removed from the Credential Manager.": "Chave removida do Gerenciador de Credenciais.",
    "Testing…": "Testando…", "Generating {n} pack(s) in the background…": "Gerando {n} pacote(s) em segundo plano…",
    "Mastered {n}": "Dominados {n}", "Reviews {n}": "Revisões {n}", "All": "Todos",
    "{n} session": "{n} sessão", "{n} sessions": "{n} sessões",
    "After mastery you review the flashcards on day {days}. Each review gives +{xp} XP; if you struggle, the same review repeats the next day.":
        "Depois de dominar, você revisa os flashcards nos dias {days}. Cada revisão dá +{xp} XP; se tiver "
        "dificuldade, a mesma revisão se repete no dia seguinte.",
    "What do you remember about this chapter?": "O que você lembra deste capítulo?",
    "Stage {stage}: {focus}. Answer from memory — type it and let Gemini check it, or reveal the model answer.":
        "Etapa {stage}: {focus}. Responda de memória — digite e deixe o Gemini corrigir, ou revele a resposta modelo.",
    "(no answer written)": "(sem resposta escrita)", "Save an API key first.": "Salve uma chave da API primeiro.",
    "New chapter / topic…": "Novo capítulo / tema…", "Review due ({n})": "Revisão pendente ({n})",
    "Topic / Chapter": "Tema / Capítulo", "Course / Source": "Curso / Fonte",
    "Spaced-repetition reviews after mastery (turn off for projects)":
        "Revisões espaçadas depois de dominar (desligue para projetos)",
    "Reopen chapter?": "Reabrir capítulo?",
    "Leaving 'Mastered' removes its +{xp} XP and pending reviews (you get them back when you master it again).":
        "Sair de 'Dominado' remove os +{xp} XP e as revisões pendentes (você os recupera quando dominar de novo).",
    "Where did you stop? What's next?": "Onde você parou? Qual é o próximo passo?",
    "What did you study? Notes, insights, doubts, code…": "O que você estudou? Notas, percepções, dúvidas, código…",
    "Time spent": "Tempo gasto", "Session logged! +{xp} XP 🔥": "Sessão registrada! +{xp} XP 🔥",
    "JOURNAL ({n})": "DIÁRIO ({n})", "Notes": "Notas", "Next step": "Próximo passo",
    "Notes can't be empty and the date must be DD/MM/YYYY.": "As notas não podem ficar vazias e a data deve ser DD/MM/AAAA.",
    "due {date}": "para {date}", "Gemini is writing your deep review…": "O Gemini está escrevendo sua revisão aprofundada…",
    "Type an answer first.": "Digite uma resposta primeiro.",
    "AI review pack is queued — these are your own flashcards for now.":
        "O pacote de revisão com IA está na fila — por enquanto, estes são seus próprios flashcards.",
    "AI review pack is being generated — these are your own flashcards for now.":
        "O pacote de revisão com IA está sendo gerado — por enquanto, estes são seus próprios flashcards.",
    "AI review pack failed ({error}) — using your flashcards.":
        "O pacote de revisão com IA falhou ({error}) — usando seus flashcards.",
    "No flashcards yet — try to explain the topic out loud, then check the summary below.":
        "Ainda sem flashcards — tente explicar o tema em voz alta e depois confira o resumo abaixo.",
    "(empty)": "(vazio)", "Mastered on {date}": "Dominado em {date}", "Wrap-up incomplete": "Fechamento incompleto",
    "These parts of the wrap-up are still empty: {parts}.\nYour reviews use them. Master the chapter anyway?":
        "Estas partes do fechamento ainda estão vazias: {parts}.\nSuas revisões usam elas. Dominar o capítulo mesmo assim?",
    "Write something about this session first.": "Escreva algo sobre esta sessão primeiro.",
    "Invalid date (use DD/MM/YYYY).": "Data inválida (use DD/MM/AAAA).",
    "Session logged (write {n}+ characters to earn XP).": "Sessão registrada (escreva {n}+ caracteres para ganhar XP).",
    "Session logged (today's XP for this chapter already earned).":
        "Sessão registrada (o XP de hoje deste capítulo já foi ganho).",
    "No entries yet. Log what you study as you go — the wrap-up comes at the end.":
        "Ainda sem registros. Registre o que estudar conforme avança — o fechamento vem no final.",
    "Reviews are turned off for this chapter (e.g. a project). Tick the checkbox above to turn them on.":
        "As revisões estão desligadas para este capítulo (ex.: um projeto). Marque a caixa acima para ligá-las.",
    "Reviews start once the chapter is mastered.": "As revisões começam quando o capítulo for dominado.",
    " • done {date}": " • feita {date}", "Regenerate": "Gerar de novo",
    "AI deep review: add your Gemini API key to generate harder, stage-by-stage questions.":
        "Revisão aprofundada com IA: adicione sua chave do Gemini para gerar perguntas mais difíceis, etapa por etapa.",
    "Gemini is checking your answer…": "O Gemini está corrigindo sua resposta…", "Later": "Depois",
    "Struggled — repeat tomorrow (+{xp} XP)": "Tive dificuldade — repetir amanhã (+{xp} XP)",
    "Remembered (+{xp} XP)": "Lembrei (+{xp} XP)", "Study Chapters": "Capítulos de estudo",
    "No reviews (project)": "Sem revisões (projeto)", "Next review {date}": "Próxima revisão {date}",
    "Delete chapter": "Excluir capítulo", "Set stage: {stage}": "Definir etapa: {stage}",
    "Start studying": "Começar a estudar", "Ready to wrap up": "Pronto para fechar",
    "Mark as mastered (+{xp} XP)": "Marcar como dominado (+{xp} XP)", "Master anyway": "Dominar mesmo assim",
    "Edit journal entry": "Editar registro do diário",
    "🎉 All reviews complete — this one is in long-term memory.":
        "🎉 Todas as revisões concluídas — isto está na memória de longo prazo.",
    "No review scheduled.": "Nenhuma revisão agendada.", "Start review schedule": "Iniciar agenda de revisões",
    "AI deep review ready — {n} questions across {stages} stages":
        "Revisão aprofundada pronta — {n} perguntas em {stages} etapas",
    "Last regeneration failed: {error}": "A última geração falhou: {error}", "AI settings": "Configurações de IA",
    "AI deep review failed ({n} attempt(s)): {error}": "A revisão aprofundada falhou ({n} tentativa(s)): {error}",
    "No AI deep review for this chapter yet.": "Ainda não há revisão aprofundada com IA para este capítulo.",
    "AI review settings": "Configurações da revisão com IA", "AI review settings (Gemini)": "Configurações da revisão com IA (Gemini)",
    "Add chapter": "Adicionar capítulo", "Reviews complete": "Revisões concluídas",
    "NEW JOURNAL ENTRY": "NOVO REGISTRO NO DIÁRIO",
    "Fill this in when you finish studying — it's your proof of understanding and what your spaced-repetition reviews will quiz you on.":
        "Preencha quando terminar de estudar — é a sua prova de entendimento e o que as revisões espaçadas vão perguntar.",
    ", {n} gap(s) found in your notes": ", {n} lacuna(s) encontrada(s) nas suas notas",
    "Retry now": "Tentar agora", "Generate now": "Gerar agora", "Show answer": "Mostrar resposta",
    "Review {n} of {total}": "Revisão {n} de {total}", "Delete chapter?": "Excluir capítulo?",
    "'{topic}', its journal and its pending reviews will be removed.":
        "'{topic}', seu diário e suas revisões pendentes serão removidos.",
    "Journal ({n})": "Diário ({n})", "Wrap-up": "Fechamento", " • AI deep review": " • revisão aprofundada com IA",
    "Show all answers & summary": "Mostrar todas as respostas e o resumo",
    "Generate missing packs ({n})": "Gerar pacotes que faltam ({n})",
    "Get a free key at Google AI Studio (aistudio.google.com → Get API key). When a pack is generated, the chapter's journal and wrap-up are sent to Google's Gemini API; on the free tier Google may use that content to improve its products.":
        "Consiga uma chave grátis no Google AI Studio (aistudio.google.com → Get API key). Quando um pacote é gerado, "
        "o diário e o fechamento do capítulo são enviados à API do Gemini do Google; no plano gratuito, o Google pode "
        "usar esse conteúdo para melhorar seus produtos.",
    "{n} review due — start": "{n} revisão pendente — começar", "{n} reviews due — start": "{n} revisões pendentes — começar",
    "Add a chapter on the left to start your study journal.": "Adicione um capítulo à esquerda para começar seu diário de estudos.",
    "Reviews": "Revisões", "WHERE I STOPPED / NEXT STEP": "ONDE PAREI / PRÓXIMO PASSO",
    "Log session (+{xp} XP)": "Registrar sessão (+{xp} XP)", "Delete journal entry?": "Excluir registro do diário?",
    "Review {n}": "Revisão {n}", " ({n} due)": " ({n} pendente(s))", "last: {date}": "última: {date}",
    "Review now": "Revisar agora", "planned ~{date}": "prevista ~{date}", "Test connection": "Testar conexão",
    "Remove saved key": "Remover chave salva",
})

# ------------------------------------------------------------------ calendar
PT.update({
    "Cyan": "Ciano", "Blue": "Azul", "Green": "Verde", "Amber": "Âmbar", "Orange": "Laranja", "Red": "Vermelho",
    "Pink": "Rosa", "Purple": "Roxo", "Grey": "Cinza",
    "15 min": "15 min", "30 min": "30 min", "45 min": "45 min", "1 hour": "1 hora", "1h 30min": "1h 30min",
    "2 hours": "2 horas", "3 hours": "3 horas", "4 hours": "4 horas", "8 hours": "8 horas",
    "No reminder": "Sem lembrete", "At start time": "Na hora do início", "5 min before": "5 min antes",
    "10 min before": "10 min antes", "15 min before": "15 min antes", "30 min before": "30 min antes",
    "1 hour before": "1 hora antes", "2 hours before": "2 horas antes", "1 day before": "1 dia antes",
    "On the day (09:00)": "No dia (09:00)", "The day before (09:00)": "Na véspera (09:00)",
    "expires": "vence", "expired": "venceu", "renewal reminder": "lembrete de renovação",
    "All day": "Dia inteiro", ", until {date}": ", até {date}", "{n} min before": "{n} min antes",
    "Agenda from {day} {month} {year}": "Agenda a partir de {day} {month} {year}",
    "Does not repeat": "Não repete", "Every day": "Todo dia", "Every weekday (Mon–Fri)": "Todo dia útil (seg–sex)",
    "Weekly on {day}": "Semanal ({day})", "Yearly on {n} {month}": "Anual em {n} de {month}",
    "Search: \"{text}\"": "Busca: \"{text}\"", "Delete repeating event": "Excluir evento que se repete",
    "'{title}' repeats. What do you want to delete?": "'{title}' se repete. O que você quer excluir?",
    "Monthly on day {n}": "Mensal no dia {n}", "{start} – {end} {month} {year}": "{start} – {end} de {month} de {year}",
    "{type} • expires {date}": "{type} • vence em {date}",
    "Search events (title or notes)…": "Buscar eventos (título ou notas)…",
    "No events match \"{text}\".": "Nenhum evento corresponde a \"{text}\".",
    "Nothing scheduled in the next {n} days.": "Nada agendado nos próximos {n} dias.",
    "Delete event?": "Excluir evento?", "'{title}' will be removed.": "'{title}' será removido.",
    "Title": "Título", "Date (DD/MM/YYYY)": "Data (DD/MM/AAAA)", "Duration": "Duração", "Repeat": "Repetir",
    "Until (optional)": "Até (opcional)", "Reminder": "Lembrete", "Edit repeating event": "Editar evento que se repete",
    "'{title}' repeats. Apply the changes to:": "'{title}' se repete. Aplicar as mudanças a:",
    " (or last day)": " (ou o último dia)", "📚 Review: {topic}": "📚 Revisão: {topic}", "Study review {n}": "Revisão de estudo {n}",
    "+{n} more": "+{n} mais", "{n} event(s) – open day": "{n} evento(s) – abrir o dia", "Open day": "Abrir o dia",
    "Done (+{xp} XP earned)": "Feito (+{xp} XP ganhos)", "Not done yet": "Ainda não feito",
    "⚠ Overlaps with: {titles}": "⚠ Conflita com: {titles}", "Give the event a title.": "Dê um título ao evento.",
    "Invalid date. Use DD/MM/YYYY.": "Data inválida. Use DD/MM/AAAA.", " (overdue)": " (atrasada)",
    "DAY SUMMARY": "RESUMO DO DIA", "{n} event(s) • {done} done • +{xp} XP": "{n} evento(s) • {done} feito(s) • +{xp} XP",
    "Nothing scheduled. Click an hour to add an event.": "Nada agendado. Clique em um horário para adicionar um evento.",
    "Invalid 'Until' date. Use DD/MM/YYYY.": "Data 'Até' inválida. Use DD/MM/AAAA.",
    "'Until' must be on or after the event date.": "'Até' deve ser na data do evento ou depois.",
    "all-day": "dia inteiro", "New event at {time}": "Novo evento às {time}",
    "{verb} this event": "{verb} este evento", "{verb} this and following": "{verb} este e os seguintes",
    "{verb} all events": "{verb} todos os eventos", "Edit event": "Editar evento", "New event": "Novo evento",
    "Month": "Mês", "Week": "Semana", "Day": "Dia", "Agenda": "Agenda", "Start review": "Começar revisão", "Open": "Abrir",
    "Press Enter to search the past and next 12 months": "Aperte Enter para buscar nos 12 meses anteriores e seguintes",
    "Undo done": "Desfazer", "Mark done (+{xp} XP)": "Marcar como feito (+{xp} XP)", "Review: {topic}": "Revisão: {topic}",
    "Mark as done (+{xp} XP)": "Marcar como feito (+{xp} XP)", "Color": "Cor",
    " • overdue since {date}": " • atrasada desde {date}", "Pick a date": "Escolher uma data",
})

# ------------------------------------------------------------------ documents
PT.update({
    "Identity": "Identidade", "Vehicle": "Veículo", "Home": "Casa", "Other": "Outro",
    "Valid until {date}": "Válido até {date}", "{n} days before": "{n} dias antes",
    "Expired {n} day ago": "Venceu há {n} dia", "Expired {n} days ago": "Venceu há {n} dias", "Expires today": "Vence hoje",
    "Expires in {n} day": "Vence em {n} dia", "Expires in {n} days": "Vence em {n} dias",
    "{n} year before": "{n} ano antes", "{n} years before": "{n} anos antes", "{n} months before": "{n} meses antes",
    "PIN": "PIN", "Wrong PIN.": "PIN errado.", "New expiration date (DD/MM/YYYY)": "Nova data de vencimento (DD/MM/AAAA)",
    "Use DD/MM/YYYY.": "Use DD/MM/AAAA.",
    "The new expiration date should be in the future.": "A nova data de vencimento deve estar no futuro.",
    "{n} renewal quest added to your Quest Log.": "{n} missão de renovação adicionada ao seu Diário de missões.",
    "{n} renewal quests added to your Quest Log.": "{n} missões de renovação adicionadas ao seu Diário de missões.",
    "Renewed": "Renovei", "Reminder from {date} ({lead})": "Lembrete a partir de {date} ({lead})",
    "Copy (clipboard clears in {n}s)": "Copiar (a área de transferência é limpa em {n}s)",
    "Notes saved • unlock to view": "Notas salvas • desbloqueie para ver",
    "Renewed! +{xp} XP from the renewal quest 🎉": "Renovado! +{xp} XP da missão de renovação 🎉",
    "Renewed — reminders reset.": "Renovado — lembretes reiniciados.",
    "Name (e.g. My CNH, Honda Civic IPVA)": "Nome (ex.: Minha CNH, IPVA do Honda Civic)",
    "Expiration date (DD/MM/YYYY)": "Data de vencimento (DD/MM/AAAA)", "Remind me": "Me lembrar",
    "Renews every year (IPVA, licensing, IPTU, insurance…)": "Renova todo ano (IPVA, licenciamento, IPTU, seguro…)",
    "Number (optional — encrypted)": "Número (opcional — criptografado)",
    "Notes (optional — encrypted)": "Notas (opcional — criptografadas)",
    "A name and a valid expiration date (DD/MM/YYYY) are required.":
        "Um nome e uma data de vencimento válida (DD/MM/AAAA) são obrigatórios.",
    "Create a renewal quest when a document needs attention": "Criar uma missão de renovação quando um documento precisar de atenção",
    "Current PIN": "PIN atual", "New PIN (4-8 digits)": "Novo PIN (4-8 dígitos)", "Repeat new PIN": "Repita o novo PIN",
    "PIN saved — numbers and notes are now locked.": "PIN salvo — números e notas agora estão bloqueados.",
    "PIN removed.": "PIN removido.", "Forgot the PIN?": "Esqueceu o PIN?",
    "The PIN is removed AND every saved number and note is erased (names and dates stay). This can't be undone.":
        "O PIN é removido E todo número e nota salvos são apagados (nomes e datas ficam). Não dá para desfazer.",
    "NEEDS ATTENTION": "PRECISA DE ATENÇÃO", "ALL GOOD": "TUDO CERTO", "No PIN set": "Sem PIN",
    "Unlock to edit": "Desbloqueie para editar", "Current PIN is wrong.": "O PIN atual está errado.",
    "The PIN must have 4 to 8 digits.": "O PIN deve ter de 4 a 8 dígitos.", "The two PINs don't match.": "Os dois PINs não batem.",
    "Type the current PIN to remove it.": "Digite o PIN atual para removê-lo.", "Erase and reset": "Apagar e redefinir",
    "Change PIN": "Trocar PIN", "Set PIN": "Definir PIN", "Remove PIN": "Remover PIN", "Forgot PIN": "Esqueci o PIN",
    "Old documents removed — {n} imported (name, type and date only).":
        "Documentos antigos removidos — {n} importados (só nome, tipo e data).",
    "Old documents deleted.": "Documentos antigos excluídos.", "Unlock": "Desbloquear", "Lock now": "Bloquear agora",
    "Unlock numbers & notes": "Desbloquear números e notas", "Renewal history": "Histórico de renovações",
    "Number saved • unlock to view": "Número salvo • desbloqueie para ver", "Renewals: {title}": "Renovações: {title}",
    "Documents settings": "Configurações dos documentos", "Renewed: {title}": "Renovado: {title}",
    "Add document": "Adicionar documento", "Yearly": "Anual", "Renewal quest in your Quest Log": "Missão de renovação no seu Diário de missões",
    "Delete document?": "Excluir documento?",
    "'{title}' and its renewal history will be removed permanently.":
        "'{title}' e seu histórico de renovações serão removidos para sempre.",
    "Hide": "Ocultar", "Show": "Mostrar", "Edit document": "Editar documento",
    "PIN reset — saved numbers and notes were erased.": "PIN redefinido — os números e notas salvos foram apagados.",
    "Import keeps only the name, type and expiration date; the old rows (numbers included) are then deleted for good. Daily backups keep a copy for up to 14 days.":
        "A importação guarda só o nome, o tipo e a data de vencimento; as linhas antigas (com números) são então "
        "excluídas para sempre. Os backups diários guardam uma cópia por até 14 dias.",
    "Unlock documents": "Desbloquear documentos", "PIN & renewal quests": "PIN e missões de renovação",
    "Numbers and notes stay visible for {n} minutes.": "Números e notas ficam visíveis por {n} minutos.",
    "If a renewal quest is open for it, it will be completed (+XP).":
        "Se houver uma missão de renovação aberta para ele, ela será concluída (+XP).",
    "Reminder starts {date} ({lead})": "O lembrete começa em {date} ({lead})",
    "Track what expires: CNH, passport, IPVA, insurance…": "Acompanhe o que vence: CNH, passaporte, IPVA, seguro…",
    "Only a name, type and expiration date are needed.": "Só são necessários nome, tipo e data de vencimento.",
    "{n} document from the old format (with numbers and extra fields) is still stored.":
        "{n} documento do formato antigo (com números e campos extras) ainda está guardado.",
    "{n} documents from the old format (with numbers and extra fields) are still stored.":
        "{n} documentos do formato antigo (com números e campos extras) ainda estão guardados.",
    "Import without numbers": "Importar sem números", "Delete all": "Excluir todos",
    "Previous expiration: {date}": "Vencimento anterior: {date}",
    "Optional — only if you really need it here:": "Opcional — só se você realmente precisar disso aqui:",
    "PIN lock": "Bloqueio por PIN",
    "Hides numbers and notes until you type the PIN (they are already encrypted on disk; the PIN keeps them off the screen).":
        "Oculta números e notas até você digitar o PIN (eles já ficam criptografados no disco; o PIN os tira da tela).",
    " • renews every year": " • renova todo ano", "+{n} year": "+{n} ano", "+{n} years": "+{n} anos", " • yearly": " • anual",
    "Import and delete old documents?": "Importar e excluir documentos antigos?",
    "Names, types and expiration dates are imported; numbers, notes and extra fields are deleted.":
        "Nomes, tipos e datas de vencimento são importados; números, notas e campos extras são excluídos.",
    "Delete old documents?": "Excluir documentos antigos?",
    "All {n} old-format documents are deleted permanently.": "Todos os {n} documentos do formato antigo serão excluídos para sempre.",
    "Import": "Importar", "Check what's needed to renew {type}": "Ver o que é preciso para renovar {type}",
    "Renew {title}": "Renovar {title}", "Created automatically: {title} ({type}) expires on {date}.":
        "Criada automaticamente: {title} ({type}) vence em {date}.",
    "Renew {type}": "Renovar {type}", "Press 'Renewed' in Documents with the new date":
        "Apertar 'Renovei' em Documentos com a nova data",
})

# ------------------------------------------------------------------ wallpaper (settings screen + desktop HUD)
PT.update({
    "Amber / Gold": "Âmbar / Dourado", "Neon Green": "Verde neon", "Crimson": "Carmesim",
    "Top-Right": "Superior direito", "Top-Left": "Superior esquerdo", "Bottom-Right": "Inferior direito",
    "Bottom-Left": "Inferior esquerdo", "Top-Center": "Superior central", "Center": "Centro",
    "Pure Black (Minimalist)": "Preto puro (minimalista)", "Custom Image (base_wallpaper.jpg)": "Imagem própria (base_wallpaper.jpg)",
    "Rotate images from a folder": "Alternar imagens de uma pasta",
    "Compact": "Compacto", "Large": "Grande",
    "Streak & today's score": "Sequência e nota de hoje", "Level & XP bar": "Nível e barra de XP",
    "Insight of the day (Gemini)": "Insight do dia (Gemini)", "Active quests": "Missões em andamento",
    "Studies & reviews due": "Estudos e revisões pendentes", "Upcoming calendar": "Próximos compromissos",
    "Document alerts": "Alertas de documentos",
    "Updating…": "Atualizando…", "Applied to your desktop.": "Aplicado na sua área de trabalho.", "HUD resumed.": "HUD retomado.",
    "Gemini is writing today's insight…": "O Gemini está escrevendo o insight de hoje…",
    "Paused — your original wallpaper is back.": "Pausado — seu papel de parede original voltou.",
    "Paused. (No copy of your original wallpaper was found, so the current one stays.)":
        "Pausado. (Não achei uma cópia do seu papel de parede original, então o atual continua.)",
    "The folder picker isn't available here — paste the folder path instead.":
        "O seletor de pastas não está disponível aqui — cole o caminho da pasta.",
    "Layout": "Layout", "Background": "Fundo",
    "Blocks with nothing to show (no events, no alerts…) are hidden automatically.":
        "Blocos sem nada para mostrar (sem eventos, sem alertas…) somem automaticamente.",
    "Blocks (order = top to bottom)": "Blocos (ordem = de cima para baixo)",
    "This is how your desktop will look.": "É assim que sua área de trabalho vai ficar.", "Folder": "Pasta",
    r"e.g. C:\Users\you\Pictures\Wallpapers": r"ex.: C:\Users\voce\Pictures\Wallpapers",
    "A new image each day (in name order). Images fill the screen without being stretched.":
        "Uma imagem nova por dia (em ordem de nome). As imagens preenchem a tela sem ficar esticadas.",
    "Today: “{text}”": "Hoje: “{text}”", "Preview failed: {error}": "A prévia falhou: {error}",
    "Folder with wallpaper images": "Pasta com imagens de papel de parede", "Desktop Wallpaper HUD": "HUD do papel de parede",
    "Text scales with your screen resolution automatically (sharp on 1440p / 4K).":
        "O texto se ajusta à resolução da tela automaticamente (nítido em 1440p / 4K).",
    "Next image": "Próxima imagem", "needs a Gemini key (Options → AI)": "precisa de uma chave do Gemini (Opções → IA)",
    "Columns": "Colunas", "Size": "Tamanho", "Browse…": "Procurar…",
    "{n} image found": "{n} imagem encontrada", "{n} images found": "{n} imagens encontradas", "writing…": "escrevendo…",
    "Move block up": "Subir bloco", "Move block down": "Descer bloco", "Position": "Posição", "Accent color": "Cor de destaque",
    " • today: {name}": " • hoje: {name}", "Preview": "Prévia", "Apply now": "Aplicar agora",
    "New insight for today": "Novo insight para hoje",
    "Paused — your own wallpaper is showing.": "Pausado — seu próprio papel de parede está aparecendo.",
    "Active — refreshes when you log things and every hour.": "Ativo — atualiza quando você registra algo e a cada hora.",
    "Pause & restore my wallpaper": "Pausar e restaurar meu papel de parede",
    # desktop HUD
    "DAILY GAMIFICATION HUD": "HUD DE GAMIFICAÇÃO DIÁRIA", "Today: {score} / 10": "Hoje: {score} / 10",
    "INSIGHT OF THE DAY:": "INSIGHT DO DIA:", "ACTIVE QUESTS:": "MISSÕES EM ANDAMENTO:", "STUDIES:": "ESTUDOS:",
    "UPCOMING CALENDAR:": "PRÓXIMOS COMPROMISSOS:", "DOCUMENT ALERTS:": "ALERTAS DE DOCUMENTOS:",
    "NO ENTRIES YET": "SEM REGISTROS AINDA", "Today: - / 10": "Hoje: - / 10", "PASSING": "NA META",
    "STREAK: {n} day": "SEQUÊNCIA: {n} dia", "STREAK: {n} days": "SEQUÊNCIA: {n} dias",
    "{xp} / 10 XP to Level {next} (Total: {total}/1000)": "{xp} / 10 XP para o nível {next} (Total: {total}/1000)",
    "NEUTRAL": "NEUTRO", "NEEDS FOCUS": "PRECISA DE FOCO", "All quests completed!": "Todas as missões concluídas!",
    "No active chapters right now.": "Nenhum capítulo em andamento agora.", "REVIEW DUE ({n}): ": "REVISÃO PENDENTE ({n}): ",
    "EXPIRED {n}d ago": "VENCEU há {n}d", "expires in {n}d": "vence em {n}d",
})

# ------------------------------------------------------------------ options
PT.update({
    "Text": "Texto", "Voice": "Voz", "Voice + text": "Voz + texto", "Female": "Feminina", "Male": "Masculina", "Off": "Desligado",
    "Saved. Streaks, colors and the wallpaper use the new rule.":
        "Salvo. Sequências, cores e o papel de parede usam a nova regra.",
    "Checking the token…": "Verificando o token…", "Token removed and assistant turned off.": "Token removido e assistente desligado.",
    "Unpaired. Send the new code to pair again.": "Desconectado. Envie o novo código para conectar de novo.",
    "General": "Geral", "Tabs": "Abas", "Habits & scoring": "Hábitos e pontuação", "Data": "Dados", "AI (Gemini)": "IA (Gemini)",
    "Telegram assistant": "Assistente no Telegram", "Messages it sends": "Mensagens que ele envia",
    "Could not change it: {error}": "Não deu para mudar: {error}", "That folder doesn't exist.": "Essa pasta não existe.",
    "Paste the token from @BotFather first.": "Cole primeiro o token do @BotFather.",
    "Saved — connected to @{bot}.": "Salvo — conectado a @{bot}.", "Test message sent.": "Mensagem de teste enviada.",
    "The whole app: screens, wallpaper, notifications, the Telegram assistant and what the AI writes. Your data is never changed.":
        "O app inteiro: telas, papel de parede, notificações, o assistente no Telegram e o que a IA escreve. "
        "Seus dados nunca são alterados.",
    "Closing the window keeps it running in the tray": "Fechar a janela mantém o app rodando na bandeja",
    "Off: the X button quits the app (reminders and the assistant stop with it).":
        "Desligado: o botão X fecha o app (os lembretes e o assistente param junto).",
    "Check for updates when the app starts": "Procurar atualizações ao abrir o app",
    "A turned-off tab isn't loaded at all, and its background work stops (e.g. Calendar off = no event alarms; Wallpaper off = the HUD stops updating).":
        "Uma aba desligada nem é carregada, e o trabalho dela em segundo plano para (ex.: Calendário desligado = sem "
        "alarmes de eventos; Papel de parede desligado = o HUD para de atualizar).",
    "Unavailable.": "Indisponível.",
    "1) In Telegram, talk to @BotFather → /newbot → copy the token.  2) Paste it here and save.  3) Turn the assistant on and send the pairing code to your bot.":
        "1) No Telegram, fale com o @BotFather → /newbot → copie o token.  2) Cole aqui e salve.  "
        "3) Ligue o assistente e envie o código de pareamento para o seu bot.",
    "You can always talk to it by text or by voice message. Voice replies use Microsoft's neural voices (Brazilian Portuguese or English, following the app language).":
        "Você sempre pode falar com ele por texto ou por mensagem de voz. As respostas em voz usam as vozes neurais da "
        "Microsoft (português do Brasil ou inglês, conforme o idioma do app).",
    "It can read everything and mark habits, add events, log studies and update quests — it never deletes anything. It only works while this app is running.":
        "Ele lê tudo e pode marcar hábitos, criar eventos, registrar estudos e atualizar missões — nunca apaga nada. "
        "Só funciona enquanto este app estiver aberto.",
    "The tracker will open when you sign in to Windows.": "O Tracker vai abrir quando você entrar no Windows.",
    "It won't open with Windows anymore.": "Ele não vai mais abrir junto com o Windows.",
    "Each daily backup is also copied to that folder.": "Cada backup diário também é copiado para essa pasta.",
    "Extra backup folder removed (backups stay in the data folder).":
        "Pasta extra de backup removida (os backups continuam na pasta de dados).",
    "Could not open it: {error}": "Não deu para abrir: {error}", "Exported to {path}": "Exportado para {path}",
    "Exported to your Desktop.": "Exportado para a sua Área de Trabalho.", "Export failed: {error}": "A exportação falhou: {error}",
    "Check-in sent.": "Check-in enviado.", "Nothing to ask: every habit is answered today.":
        "Nada a perguntar: todos os hábitos de hoje já foram respondidos.",
    "Pair your Telegram first.": "Conecte seu Telegram primeiro.",
    "Passing score: the daily average that keeps the streak (and turns the day green). Rest days: how many times per week each habit may take a Rest answer.":
        "Nota mínima: a média diária que mantém a sequência (e deixa o dia verde). Dias de descanso: quantas vezes por "
        "semana cada hábito pode receber a resposta Descanso.",
    "Quiet hours": "Horário silencioso",
    "No Telegram messages about documents, reviews or achievements in this window (they arrive afterwards). Times you set yourself — briefing, event reminders, the check-in — are always sent.":
        "Nenhuma mensagem no Telegram sobre documentos, revisões ou conquistas neste intervalo (elas chegam depois). "
        "Horários que você mesmo definiu — resumo da manhã, lembretes de eventos, check-in — sempre são enviados.",
    "Extra backup folder (e.g. OneDrive)": "Pasta extra de backup (ex.: OneDrive)",
    "Empty = only the data folder": "Vazio = só a pasta de dados",
    "A copy of the database is made every day before the app starts.": "Uma cópia do banco de dados é feita todo dia antes de o app abrir.",
    "One key powers study reviews, the wallpaper insight, the quest planner and the Telegram assistant (free tier is enough).":
        "Uma chave só alimenta as revisões de estudo, o insight do papel de parede, o planejador de missões e o "
        "assistente no Telegram (o plano gratuito basta).",
    "Bot token": "Token do bot",
    "Calendar reminders (each event's own reminder time)": "Lembretes do calendário (no horário de lembrete de cada evento)",
    "Documents expiring (window, 7 days, due)": "Documentos vencendo (aviso, 7 dias, no dia)",
    "Study reviews due (after 09:00)": "Revisões de estudo pendentes (depois das 09:00)",
    "Evening check-in with answer buttons": "Check-in da noite com botões de resposta",
    "Achievements (level up, streaks, quests, mastered chapters)": "Conquistas (nível, sequências, missões, capítulos dominados)",
    "Assistant unavailable.": "Assistente indisponível.", "Start with Windows": "Iniciar com o Windows",
    "Restart the app to apply.": "Reinicie o app para aplicar.", "Restart now": "Reiniciar agora",
    "Schedule (always on)": "Hábitos (sempre ligada)", "Saved ✓ (paste a new one to replace)": "Salvo ✓ (cole um novo para substituir)",
    "Paste the token from @BotFather": "Cole o token do @BotFather", "Assistant on": "Assistente ligado",
    "Save a bot token first.": "Salve um token de bot primeiro.", "👋 Test message from your tracker.": "👋 Mensagem de teste do seu Tracker.",
    "Passing score": "Nota mínima", "Rest days / habit / week": "Descansos / hábito / semana", "From": "De", "To": "Até",
    "Replies": "Respostas", "⚠ edge-tts isn't installed, so replies fall back to text.":
        "⚠ O edge-tts não está instalado, então as respostas voltam a ser em texto.",
    "Morning briefing": "Resumo da manhã",
    "Sent at the Schedule's nightly reminder time ({time}).": "Enviado no horário do lembrete noturno dos Hábitos ({time}).",
    "Turn on the nightly reminder in the Schedule tab (🔔) to pick its time.":
        "Ligue o lembrete noturno na aba Hábitos (🔔) para escolher o horário.",
    "Open data folder": "Abrir pasta de dados", "Export habits (CSV)": "Exportar hábitos (CSV)", "Gemini settings…": "Configurações do Gemini…",
    "Check and save the token": "Verificar e salvar o token", "Remove the saved token": "Remover o token salvo",
    "Send test message": "Enviar mensagem de teste", "Send check-in now": "Enviar check-in agora", "Unpair": "Desconectar",
    "Your wake-up message: today's events, reviews, documents and next quest steps, written by Gemini.":
        "Sua mensagem de bom-dia: eventos de hoje, revisões, documentos e próximos passos das missões, escrita pelo Gemini.",
    "Save backup folder": "Salvar pasta de backup", "Pairing code": "Código de pareamento",
})

# ------------------------------------------------------------------ diary
PT.update({
    # moods, energy, look back
    "Very low": "Muito baixo", "Low": "Baixo", "Okay": "Ok", "Good": "Bom", "Great": "Ótimo",
    "Drained": "Esgotado", "Steady": "Estável", "Charged": "Carregado",
    "A week ago": "Uma semana atrás", "A month ago": "Um mês atrás", "A year ago": "Um ano atrás",
    "Today's page": "Página de hoje",
    # guided exercises
    "Win of the day": "Vitória do dia",
    "Big or small: write down something that went well and own your part in it.":
        "Grande ou pequena: escreva algo que deu certo e reconheça a sua parte nisso.",
    "What went well?": "O que deu certo?",
    "e.g. Stretching felt amazing — I touched my toes for the first time":
        "ex.: O alongamento foi incrível — encostei nos pés pela primeira vez",
    "What made it possible?": "O que tornou isso possível?",
    "Your effort, a choice you made, someone who helped…": "Seu esforço, uma escolha que você fez, alguém que ajudou…",
    "How does it feel?": "Como você se sente?",
    "Three good things": "Três coisas boas",
    "Three things that went well today, and why. Small things count — that's the point.":
        "Três coisas que deram certo hoje, e por quê. Coisas pequenas contam — é essa a ideia.",
    "1. Something good": "1. Algo bom", "2. Something good": "2. Algo bom", "3. Something good": "3. Algo bom",
    "Why did they happen?": "Por que aconteceram?",
    "Expressive writing": "Escrita expressiva",
    "Write freely about something that's on your mind for about 15 minutes: what happened, how you feel and why. Don't worry about grammar or order — this is only for you.":
        "Escreva livremente por uns 15 minutos sobre algo que está na sua cabeça: o que aconteceu, como você se sente "
        "e por quê. Não se preocupe com gramática ou ordem — isto é só para você.",
    "Write freely": "Escreva livremente",
    "Thought record": "Registro de pensamentos",
    "When a feeling hits hard, slow it down: separate what happened from the story your mind told.":
        "Quando um sentimento bate forte, desacelere: separe o que aconteceu da história que sua mente contou.",
    "Situation": "Situação", "Where were you? What happened?": "Onde você estava? O que aconteceu?",
    "Automatic thought": "Pensamento automático", "What went through your mind?": "O que passou pela sua cabeça?",
    "Feeling (and how strong, 0-100)": "Sentimento (e a intensidade, 0-100)", "e.g. anxious 70": "ex.: ansioso 70",
    "Evidence that supports the thought": "Evidências a favor do pensamento",
    "Evidence that doesn't": "Evidências contra",
    "A more balanced thought": "Um pensamento mais equilibrado", "What would you tell a friend?": "O que você diria a um amigo?",
    "Feeling now (0-100)": "Sentimento agora (0-100)",
    "Worry dump": "Esvaziar a mente",
    "Before sleep, empty your head onto the page so it doesn't have to hold everything tonight.":
        "Antes de dormir, esvazie a cabeça no papel para ela não precisar segurar tudo esta noite.",
    "Everything on my mind": "Tudo o que está na minha cabeça", "What can I actually act on?": "Sobre o que eu posso agir de fato?",
    "One small next step (for tomorrow)": "Um pequeno próximo passo (para amanhã)",
    "What I can let go of for tonight": "Do que eu posso me desapegar esta noite",
    "Self-compassion letter": "Carta de autocompaixão",
    "Write to yourself the way a kind friend who knows you well would: about something hard, with understanding instead of criticism.":
        "Escreva para você mesmo como um amigo gentil que te conhece bem escreveria: sobre algo difícil, com "
        "compreensão em vez de crítica.",
    "Dear me,": "Querido eu,",
    # screens
    "Reflection": "Reflexão", "What made it special? How did it feel?": "O que tornou isso especial? Como foi?",
    "⭐ Highlight — show it in the Diary's highlights": "⭐ Destaque — mostrar nos destaques do Diário",
    "Saved {time}": "Salvo {time}", "Delete exercise?": "Excluir exercício?",
    "'{title}' of {day} will be deleted for good.": "'{title}' de {day} será excluído para sempre.",
    "From the Schedule": "Dos Hábitos", "Guided exercises": "Exercícios guiados", "Unlock to read this note": "Desbloqueie para ler esta nota",
    "{title} updated.": "{title} atualizado.", "New PIN (4+ digits)": "Novo PIN (4+ dígitos)", "Repeat the PIN": "Repita o PIN",
    "The current PIN is wrong.": "O PIN atual está errado.",
    "PIN removed and the diary's texts erased. Moods were kept.": "PIN removido e textos do diário apagados. Os humores foram mantidos.",
    "Without the PIN the diary can't be opened. Removing it ERASES every text in the diary (pages, exercises, habit notes and reflections); moods and earned XP stay. This can't be undone.":
        "Sem o PIN o diário não pode ser aberto. Removê-lo APAGA todos os textos do diário (páginas, exercícios, notas "
        "de hábitos e reflexões); os humores e o XP ganho ficam. Não dá para desfazer.",
    "{n} result for “{text}”": "{n} resultado para “{text}”", "{n} results for “{text}”": "{n} resultados para “{text}”",
    "Page": "Página",
    "What happened today? What's on your mind? Anything goes — it's encrypted and only yours.":
        "O que aconteceu hoje? O que está na sua cabeça? Vale tudo — é criptografado e só seu.",
    "+{xp} XP when you write at least {n} characters (each kind once a day, up to {max} a day).":
        "+{xp} XP quando você escreve pelo menos {n} caracteres (cada tipo uma vez por dia, até {max} por dia).",
    "{title} saved": "{title} salvo", "Something went wrong: {error}": "Algo deu errado: {error}",
    "Use at least 4 digits.": "Use pelo menos 4 dígitos.", "Erase texts and remove PIN": "Apagar textos e remover PIN",
    "Search the diary…": "Buscar no diário…", "On this day": "Neste dia", "⭐ Highlights": "⭐ Destaques",
    "Highlights and memories from past days will show up here.": "Destaques e lembranças de dias passados vão aparecer aqui.",
    "Edit note": "Editar nota",
    "No habit notes this day. In the Schedule, use ✎ on a habit (or press N) to write why it mattered.":
        "Nenhuma nota de hábito neste dia. Na aba Hábitos, use ✎ em um hábito (ou aperte N) para escrever por que importou.",
    "Optional: add a Gemini key (Options → AI) to ask for an honest reflection on a day.":
        "Opcional: adicione uma chave do Gemini (Opções → IA) para pedir uma reflexão honesta sobre um dia.",
    "Delete note": "Excluir nota", "The PINs don't match.": "Os PINs não batem.",
    "PIN saved. Your diary locks after 15 quiet minutes (or with the lock button).":
        "PIN salvo. Seu diário bloqueia depois de 15 minutos sem uso (ou com o botão de cadeado).",
    "Previous month": "Mês anterior", "Next month": "Próximo mês", "mood {emoji}": "humor {emoji}", "page": "página",
    "{n} exercise(s)": "{n} exercício(s)", "{n} habit note(s)": "{n} nota(s) de hábito", "Energy": "Energia",
    "+{xp} XP each": "+{xp} XP cada", "Not now": "Agora não", "I understand, continue": "Entendi, continuar",
    "Save PIN": "Salvar PIN", "Privacy & PIN": "Privacidade e PIN", "Clear search": "Limpar busca",
    "Last saved {time}": "Salvo pela última vez às {time}", "Reading your day…": "Lendo o seu dia…",
    "Sent only when you click.": "Enviado só quando você clica.", "Unlock your diary": "Desbloquear seu diário",
    "Before the first reflection": "Antes da primeira reflexão", "Diary privacy": "Privacidade do diário",
    "Ask for a reflection": "Pedir uma reflexão", "Reflect again": "Refletir de novo",
    "It stays open while you use it (locks after {n} quiet minutes).":
        "Ele fica aberto enquanto você usa (bloqueia depois de {n} minutos sem uso).",
    "It also appears on that day's Diary page. Encrypted like the rest of the diary.":
        "Ela também aparece na página daquele dia no Diário. Criptografada como o resto do diário.",
    "Your diary is locked": "Seu diário está bloqueado",
    "Notes from the Schedule can still be written without unlocking.": "Notas dos Hábitos ainda podem ser escritas sem desbloquear.",
    "Only when you click, the selected day's page, exercises, habit notes, habit answers and mood are sent to Google's Gemini for an honest, impartial reflection — it will point out patterns and your own part in things, not just comfort you. Nothing is sent automatically.":
        "Só quando você clica, a página do dia escolhido, os exercícios, as notas e respostas dos hábitos e o humor são "
        "enviados ao Gemini do Google para uma reflexão honesta e imparcial — ela vai apontar padrões e a sua parte nas "
        "coisas, não só te consolar. Nada é enviado automaticamente.",
    "On Gemini's free tier, Google may use that text to improve its products. Skip this for anything you wouldn't want to leave your computer.":
        "No plano gratuito do Gemini, o Google pode usar esse texto para melhorar seus produtos. Não use isto para "
        "nada que você não queira que saia do seu computador.",
    "The reflection is not therapy or medical advice. If you're struggling, talking to someone you trust or a professional helps — in Brazil, CVV answers 24h at 188 (free).":
        "A reflexão não é terapia nem conselho médico. Se estiver difícil, conversar com alguém de confiança ou com um "
        "profissional ajuda — o CVV atende 24h pelo 188 (grátis).",
    "Everything you write is encrypted on this computer. A PIN also hides the diary until you unlock it.":
        "Tudo o que você escreve é criptografado neste computador. Um PIN também esconde o diário até você desbloquear.",
    "There is no way to recover a forgotten PIN without erasing the diary's texts.":
        "Não há como recuperar um PIN esquecido sem apagar os textos do diário.",
    "Edit exercise": "Editar exercício", "Delete exercise": "Excluir exercício",
})

# ------------------------------------------------------------------ Gemini, Telegram, assistant status
PT.update({
    "A little": "Um pouco",
    "Gemini is configured.": "O Gemini está configurado.",
    "The google-genai package is not installed (pip install -r requirements.txt).":
        "O pacote google-genai não está instalado (pip install -r requirements.txt).",
    "No Gemini API key saved yet.": "Nenhuma chave da API do Gemini salva ainda.",
    "Connected — {n} usable models (will use {model} first).": "Conectado — {n} modelos utilizáveis (vai usar {model} primeiro).",
    "Set up your Gemini API key first (Options → AI).": "Configure primeiro sua chave da API do Gemini (Opções → IA).",
    "All Gemini models failed ({error}).": "Todos os modelos do Gemini falharam ({error}).",
    "Type or save an API key first.": "Digite ou salve uma chave da API primeiro.",
    "The key works, but no text models are available for it.": "A chave funciona, mas não há modelos de texto disponíveis para ela.",
    "No Gemini text models are available for this API key.": "Nenhum modelo de texto do Gemini está disponível para esta chave.",
    "Gemini free-tier quota reached for now. It will retry later.":
        "A cota gratuita do Gemini acabou por enquanto. Vai tentar de novo mais tarde.",
    "Could not reach Gemini: {error}": "Não foi possível falar com o Gemini: {error}",
    "Gemini rejected this API key.": "O Gemini recusou esta chave da API.",
    "Gemini rejected the API key. Check it in AI settings.": "O Gemini recusou a chave da API. Confira nas configurações de IA.",
    "No Telegram bot token saved yet.": "Nenhum token de bot do Telegram salvo ainda.",
    "Could not reach Telegram: {error}": "Não foi possível falar com o Telegram: {error}",
    "Telegram answered HTTP {code}": "O Telegram respondeu HTTP {code}",
    "Telegram rejected the bot token.": "O Telegram recusou o token do bot.",
    "Could not download the voice message: {error}": "Não foi possível baixar a mensagem de voz: {error}",
    "Could not create the shortcut": "Não foi possível criar o atalho",
    "Running and paired with your chat ({bot}).": "Rodando e conectado ao seu chat ({bot}).",
    "Off.": "Desligado.", "Problem: {error}": "Problema: {error}",
    "Not running (save a bot token and turn it on).": "Parado (salve um token de bot e ligue).",
    "the bot": "o bot",
    "Running. Send  /start {code}  to {bot} to pair your Telegram.":
        "Rodando. Envie  /start {code}  para {bot} para conectar seu Telegram.",
})

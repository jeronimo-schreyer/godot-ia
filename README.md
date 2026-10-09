# godot-ia

Base para hacer juegos en Godot 4 con agentes de IA: un kit de testing (`tools/gdharness`,
`addons/agent_harness`) y la skill `godot-agent-dev` con el método y las reglas de arquitectura
(de *Godot 4 Best Practices*).

## Setup

```
npx skills add gamedev-skills/awesome-gamedev-agent-skills
pip install godot-e2e pillow pytest
```

Requiere Godot 4.5+ en el PATH (o `GODOT_PATH`).

## Uso

```
python tools/gdh.py test     # tests (lint, proyecto sano, e2e, visuales)
python tools/gdh.py lint     # chequeos estáticos de GDScript
python tools/gdh.py run --window -c "print(g.sequence('look', 8, 10))"   # mirar el juego
```

Cuando termines tu proyecto, para pasarle el kit (con tus mejoras) al próximo:

```
python .\tools\gdh.py new ..\nuevo-juego --name "Nuevo Juego"
```

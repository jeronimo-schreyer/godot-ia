# CPU opponents that actually hit things

Pattern used by `scripts/ai_player.gd` in the Worms project.

## Simulate with the game's own code

- Extract the physics of anything the AI must predict into a plain class used by both the game
  and the AI (`Flight` for projectiles: `step(delta, terrain, worms)` + `simulate()`).
- For things with node logic (a walking sheep, a worm flying after a hit, a worm on a rope), run
  the real script on an **off-screen instance** that is never added to the tree: copy the state
  in, call its `_physics_process(TICK)` in a loop, read the result. No duplicated physics.
- Mirror frame order: if the game steps the controller before the worm in a frame, the
  simulation must too. Use the same fixed `TICK` (1/60).
- Effects that don't exist yet (a crater an explosion will dig) can be faked for the duration of
  a simulation (`Terrain.set_hole()` / `clear_hole()`).

## Decide

- Enumerate candidates (weapon x facing x angle x power, plus direct options like melee), score
  the outcome: enemy damage, kills, self/team damage penalties, bonus for knocking into water,
  small cost for scarce ammo, small random per-turn preference + repeat penalty for variety.
- Coarse grid first, refine around the best few.
- If nothing scores well, plan a move (walk / rope) the same way: simulate, pick the landing
  closest to an enemy, replay it, think again.
- Difficulty = noise on angle/power and picking among the top N, never a different brain.

## Keep the game smooth

- Spread evaluation over frames with a per-frame time budget (`Time.get_ticks_usec()`).
- Cache identical simulations (same speed/bounce/angle/power -> same flight).
- Pre-filter expensive predictions (only simulate a knockback if water is on that side).

## Tests that prove it

- Prediction == reality: apply an impulse for real and compare with the ghost prediction
  (within 1.5 px); replay a rope plan and compare the landing.
- Scenario tests with one unambiguous target: hits on hard, compensates wind (mutation-checked:
  fails when the simulation ignores wind), knocks into water from a cliff, ropes over a wall it
  can't walk past, sheep detonated next to the enemy.
- A CPU-vs-CPU match keeps moving and uses several weapons; a speed test on simulation CPU time.

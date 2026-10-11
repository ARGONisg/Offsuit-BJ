# Game Automation & OCR Engineering Guidelines

1. **Auto-Deal / Fast-Cycle Game State Tracking**:
   - When automating games with "Auto-Deal" or "Auto-Play", do not rely on transient setup phases (e.g., `BETTING` screens) that may be bypassed or flash in <100ms.
   - Track session outcomes deal-to-deal (at the start of active player action). Comparing bankroll at the same active phase cancels out placed bets.
   - A zero bankroll delta ($\Delta == 0$) following a completed hand must be recorded as a **PUSH (Tie)**, never discarded as an inactive state.

2. **Thermal & Resource Optimization**:
   - **Static Frame Skip**: Compute a fast in-memory perceptual comparison (e.g., 32x32 grayscale difference in RAM) to skip full-screen OCR and subprocess invocations when the screen is static.
   - **RAM-Only Processing**: Avoid writing temporary image crops to SSD/disk on high-frequency loops; process crops in RAM using `PIL.Image` or pipes.
   - **Fast-Path OCR**: Exit early on the first high-confidence numeric/character match in multi-pass OCR routines instead of exhaustively running all PSM and scaling permutations.
   - **Phase-Aware Loop Pacing**: Adjust polling sleeps based on game state (longer delays during animations or idle phases, faster polling during active decisions).

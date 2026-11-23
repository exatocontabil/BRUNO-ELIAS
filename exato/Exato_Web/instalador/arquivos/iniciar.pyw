"""Liga o Exato Web em segundo plano (sem janela), se ainda não estiver ligado. Usado ao iniciar o Windows e pelo instalador."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from supervisor import iniciar_se_preciso
iniciar_se_preciso()

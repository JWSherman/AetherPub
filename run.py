import uvicorn
import logging
from backend.app.core.config import settings

BANNER = r"""
   ___       __  __              ___       __  
  / _ | ___ / /_/ /  ___ ____   / _ \__ __/ /  
 / __ |/ -_) __/ _ \/ -_) __/  / ___/ // / _ \ 
/_/ |_|\__/\__/_//_/\__/_/    /_/   \_,_/_.__/ 
   >> Daily E-Reader EPUB 3 Digest Engine <<
"""

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    print(BANNER)
    print(f"⚡ Starting {settings.PROJECT_NAME} Web Server...")
    print(f"📖 Dashboard available at: http://127.0.0.1:8000")
    print(f"📚 Storage Directory: {settings.STORAGE_DIR}")
    print(f"📡 API Documentation: http://127.0.0.1:8000/docs\n")

    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )

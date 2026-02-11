import os
import time
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from inference.engine import Model, iso_to_flores


# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("nmt_api")


# =========================================================
# FASTAPI
# =========================================================
app = FastAPI(title="NMT API")


# =========================================================
# REQUEST SCHEMA
# =========================================================
class NMTRequest(BaseModel):
    text: str
    src_lang: str
    tgt_lang: str


# =========================================================
# MODEL CONFIG
# =========================================================
INDIC_LANGUAGES = set(iso_to_flores.keys())
REQUIRED_MODELS = {"en-indic", "indic-en", "indic-indic"}


# =========================================================
# MODEL LOADER
# =========================================================
class LocalTranslationModel:

    def __init__(self):

        self.models = {}
        root = "./checkpoints"

        if not os.path.exists(root):
            raise RuntimeError(f"Checkpoint folder not found: {root}")

        for folder in os.listdir(root):

            if folder not in REQUIRED_MODELS:
                continue

            model_path = os.path.join(root, folder, "ct2_int8_model")

            if not os.path.exists(model_path):
                raise RuntimeError(f"Missing model path: {model_path}")

            logger.info(f"Loading NMT model: {folder}")

            self.models[folder] = Model(
                model_path,
                device="cpu",
                input_lang_code_format="iso",
                model_type="ctranslate2"
            )

        if not self.models:
            raise RuntimeError("No NMT models loaded")

        logger.info("All NMT models loaded successfully")


    # -----------------------------------------------------
    # Translation routing
    # -----------------------------------------------------
    def translate(self, text: str, src: str, tgt: str) -> str:

        start = time.time()

        if src in INDIC_LANGUAGES and tgt in INDIC_LANGUAGES:

            output = self.models["indic-indic"] \
                .paragraphs_batch_translate__multilingual(
                    [[text, src, tgt]]
                )[0]

        elif src in INDIC_LANGUAGES and tgt == "en":

            output = self.models["indic-en"] \
                .paragraphs_batch_translate__multilingual(
                    [[text, src, "en"]]
                )[0]

        elif src == "en" and tgt in INDIC_LANGUAGES:

            output = self.models["en-indic"] \
                .paragraphs_batch_translate__multilingual(
                    [[text, "en", tgt]]
                )[0]

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported translation direction {src} → {tgt}"
            )

        logger.info(
            f"NMT {src}→{tgt} | Time: {time.time() - start:.3f}s"
        )

        return output


# =========================================================
# STARTUP LOAD
# =========================================================
@app.on_event("startup")
def load_models():

    global nmt_model

    try:
        nmt_model = LocalTranslationModel()
    except Exception as e:
        logger.error(f"Failed to load NMT models: {e}")
        raise e


# =========================================================
# ENDPOINT
# =========================================================
@app.post("/nmt")
def translate(req: NMTRequest):

    start_time = time.time()

    # ----------------------------
    # Input validation
    # ----------------------------
    if not req.text.strip():
        raise HTTPException(400, "Input text cannot be empty")

    if len(req.text) > 5000:
        raise HTTPException(400, "Text too long")

    try:
        translated = nmt_model.translate(
            req.text,
            req.src_lang,
            req.tgt_lang
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"NMT inference failed: {e}")
        raise HTTPException(500, "Translation failed")

    return {
        "translated_text": translated,
        "src_lang": req.src_lang,
        "tgt_lang": req.tgt_lang,
        "processing_time_sec": round(time.time() - start_time, 3)
    }

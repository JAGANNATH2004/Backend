import json
import re
from typing import List, Optional
import httpx
from app.config import settings
from app.models.ai import VoiceInterpretRequest, AudioInterpretRequest, VoiceInterpretResponse, ProductContext

class GeminiService:
    @staticmethod
    async def interpret_audio(req: AudioInterpretRequest) -> VoiceInterpretResponse:
        is_telugu = req.language.startswith("te")

        # Call Gemini multimodal audio API
        if settings.GEMINI_API_KEY:
            try:
                result = await GeminiService._call_gemini_audio_api(
                    audio_base64=req.audio_base64,
                    mime_type=req.mime_type,
                    is_telugu=is_telugu,
                    products=req.available_products,
                )
                if result:
                    return result
            except Exception as e:
                pass

        return VoiceInterpretResponse(
            action_type="unknown",
            explanation="క్షమించండి, మీ వాయిస్ రికార్డింగ్ అర్థం కాలేదు. దయచేసి మళ్లీ ప్రయత్నించండి." if is_telugu else "Could not transcribe or understand the audio. Please try speaking again.",
            raw_speech="",
        )

    @staticmethod
    async def _call_gemini_audio_api(
        audio_base64: str,
        mime_type: str,
        is_telugu: bool,
        products: List[ProductContext],
    ) -> Optional[VoiceInterpretResponse]:
        products_json = [
            {
                "id": p.id,
                "name": p.name,
                "unit": p.unit,
                "purchase_price": p.purchase_price,
                "selling_price": p.selling_price,
                "current_stock": p.current_stock,
            }
            for p in products
        ]

        system_instruction = (
            "You are Vyapari AI's core voice inventory assistant for small retail Kirana grocery stores in Andhra Pradesh & Telangana.\n"
            "You receive an audio recording of a shopkeeper speaking in Telugu, Indian English, or mixed Telugu-English.\n\n"
            "Your tasks:\n"
            "1. Transcribe the exact words spoken by the user in the audio into 'raw_speech'.\n"
            "2. Identify the inventory action and match against available store products:\n"
            f"{json.dumps(products_json, ensure_ascii=False)}\n\n"
            "Action Types:\n"
            "- 'add_stock': stock received or purchased (e.g. '100 packets vachayi', 'received 20 packets')\n"
            "- 'record_sale': items sold to customer (e.g. '10 Parle-G ammanu', 'sold 2 packets')\n"
            "- 'check_stock': asking how much stock is left (e.g. 'sugar entha undi?')\n"
            "- 'check_sales': asking for today's sales revenue\n"
            "- 'check_reorders': asking which items to order\n"
            "- 'unknown': audio is silent, unclear, or not related to inventory.\n\n"
            "Return valid JSON matching this schema:\n"
            "{\n"
            '  "raw_speech": "Exact transcribed text of spoken audio",\n'
            '  "action_type": "add_stock" | "record_sale" | "check_stock" | "check_sales" | "check_reorders" | "unknown",\n'
            '  "product_id": string or null,\n'
            '  "product_name": string,\n'
            '  "quantity": number,\n'
            '  "unit": string,\n'
            '  "unit_price": number or null,\n'
            '  "telugu_translation": string,\n'
            '  "explanation": string,\n'
            '  "confidence": number\n'
            "}"
        )

        model = settings.GEMINI_MODEL
        if not model or model == "gemini-2.0-flash-lite":
            model = "gemini-2.0-flash"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": audio_base64,
                            }
                        },
                        {
                            "text": f"Transcribe this audio recording and extract the Kirana store inventory action. The user's preferred language is {'Telugu' if is_telugu else 'English'}."
                        }
                    ]
                }
            ],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200 and model != "gemini-1.5-flash":
                # Fallback to gemini-1.5-flash
                fallback_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
                resp = await client.post(fallback_url, json=payload)

            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content_text = candidates[0]["content"]["parts"][0]["text"]
                    parsed = json.loads(content_text)

                    pid = parsed.get("product_id")
                    pname = parsed.get("product_name") or ""
                    unit = parsed.get("unit") or "Packets"
                    unit_price = parsed.get("unit_price")

                    matched_prod = None
                    if pid:
                        matched = [p for p in products if p.id == pid]
                        if matched:
                            matched_prod = matched[0]
                    if not matched_prod and pname:
                        pname_lower = pname.lower()
                        for p in products:
                            if p.name.lower() in pname_lower or pname_lower in p.name.lower():
                                matched_prod = p
                                break

                    if matched_prod:
                        pid = matched_prod.id
                        pname = matched_prod.name
                        unit = matched_prod.unit
                        unit_price = matched_prod.selling_price if parsed.get("action_type") == "record_sale" else matched_prod.purchase_price

                    qty = float(parsed.get("quantity", 0.0) or 0.0)
                    expected_balance = None
                    if matched_prod:
                        if parsed.get("action_type") == "add_stock":
                            expected_balance = (matched_prod.current_stock or 0.0) + qty
                        elif parsed.get("action_type") == "record_sale":
                            expected_balance = (matched_prod.current_stock or 0.0) - qty

                    return VoiceInterpretResponse(
                        action_type=parsed.get("action_type", "unknown"),
                        product_id=pid,
                        product_name=pname,
                        quantity=qty,
                        unit=unit,
                        unit_price=unit_price,
                        expected_stock_balance=expected_balance,
                        confidence=float(parsed.get("confidence", 0.95)),
                        telugu_translation=parsed.get("telugu_translation", ""),
                        explanation=parsed.get("explanation", ""),
                        raw_speech=parsed.get("raw_speech", ""),
                    )
        return None

    @staticmethod
    async def interpret_voice(req: VoiceInterpretRequest) -> VoiceInterpretResponse:
        raw_text = req.text.strip()
        is_telugu = req.language.startswith("te")

        # 1. Attempt Google Gemini Flash-Lite via REST API with JSON mode
        if settings.GEMINI_API_KEY:
            try:
                result = await GeminiService._call_gemini_api(raw_text, is_telugu, req.available_products)
                if result:
                    return result
            except Exception as e:
                # Fallback to local rule-based NLP if API call fails
                pass

        # 2. Rule-based NLP fallback
        return GeminiService._fallback_nlp(raw_text, is_telugu, req.available_products)

    @staticmethod
    async def _call_gemini_api(
        text: str,
        is_telugu: bool,
        products: List[ProductContext],
    ) -> Optional[VoiceInterpretResponse]:
        products_json = [
            {
                "id": p.id,
                "name": p.name,
                "unit": p.unit,
                "purchase_price": p.purchase_price,
                "selling_price": p.selling_price,
                "current_stock": p.current_stock,
            }
            for p in products
        ]

        system_instruction = (
            "You are Vyapari AI's core inventory assistant for small retail grocery stores in Andhra Pradesh & Telangana. "
            "You extract stock management actions from natural Telugu and Indian English speech.\n"
            "Action Types: 'add_stock' (stock received/inward), 'record_sale' (items sold/outward), "
            "'check_stock' (how much left), 'check_sales' (today's revenue), 'check_reorders' (what to buy), 'unknown'.\n"
            "Return JSON matching this schema:\n"
            "{\n"
            '  "action_type": "add_stock" | "record_sale" | "check_stock" | "check_sales" | "check_reorders" | "unknown",\n'
            '  "product_id": string or null,\n'
            '  "product_name": string,\n'
            '  "quantity": number,\n'
            '  "unit": string,\n'
            '  "unit_price": number or null,\n'
            '  "telugu_translation": string,\n'
            '  "explanation": string,\n'
            '  "confidence": number\n'
            "}"
        )

        user_prompt = (
            f"Recognized Speech: \"{text}\"\n"
            f"Available Store Products: {json.dumps(products_json, ensure_ascii=False)}\n"
            f"User preferred language: {'Telugu' if is_telugu else 'English'}"
        )

        model = settings.GEMINI_MODEL or "gemini-2.0-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"

        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    content_text = candidates[0]["content"]["parts"][0]["text"]
                    parsed = json.loads(content_text)

                    # Match product ID from available products if missing
                    pid = parsed.get("product_id")
                    pname = parsed.get("product_name") or ""
                    unit = parsed.get("unit") or "Packets"
                    unit_price = parsed.get("unit_price")

                    matched_prod = None
                    if pid:
                        matched = [p for p in products if p.id == pid]
                        if matched:
                            matched_prod = matched[0]
                    if not matched_prod and pname:
                        pname_lower = pname.lower()
                        for p in products:
                            if p.name.lower() in pname_lower or pname_lower in p.name.lower():
                                matched_prod = p
                                break

                    if matched_prod:
                        pid = matched_prod.id
                        pname = matched_prod.name
                        unit = matched_prod.unit
                        unit_price = matched_prod.selling_price if parsed.get("action_type") == "record_sale" else matched_prod.purchase_price

                    qty = float(parsed.get("quantity", 0.0) or 0.0)
                    expected_balance = None
                    if matched_prod:
                        if parsed.get("action_type") == "add_stock":
                            expected_balance = (matched_prod.current_stock or 0.0) + qty
                        elif parsed.get("action_type") == "record_sale":
                            expected_balance = (matched_prod.current_stock or 0.0) - qty

                    return VoiceInterpretResponse(
                        action_type=parsed.get("action_type", "unknown"),
                        product_id=pid,
                        product_name=pname,
                        quantity=qty,
                        unit=unit,
                        unit_price=unit_price,
                        expected_stock_balance=expected_balance,
                        confidence=float(parsed.get("confidence", 0.95)),
                        telugu_translation=parsed.get("telugu_translation", ""),
                        explanation=parsed.get("explanation", ""),
                        raw_speech=text,
                    )
        return None

    @staticmethod
    def _fallback_nlp(
        text: str,
        is_telugu: bool,
        products: List[ProductContext],
    ) -> VoiceInterpretResponse:
        lower = text.lower()

        # Find product
        matched_prod: Optional[ProductContext] = None
        for p in products:
            p_name_lower = p.name.lower()
            if p_name_lower in lower:
                matched_prod = p
                break

        if not matched_prod:
            words = [w for w in lower.split() if len(w) > 2]
            for p in products:
                p_name_lower = p.name.lower()
                for w in words:
                    if w in p_name_lower:
                        matched_prod = p
                        break
                if matched_prod:
                    break

        # Extract quantity
        qty = 1.0
        nums = re.findall(r"\b\d+(?:\.\d+)?\b", text)
        if nums:
            try:
                qty = float(nums[0])
            except Exception:
                qty = 1.0

        p_name = matched_prod.name if matched_prod else "Product"
        pid = matched_prod.id if matched_prod else None
        unit = matched_prod.unit if matched_prod else "Units"
        curr_stock = (matched_prod.current_stock or 0.0) if matched_prod else 0.0

        # Inward Stock
        if any(w in lower for w in ["వచ్చాయి", "చేర్చండి", "received", "bought", "add stock"]):
            return VoiceInterpretResponse(
                action_type="add_stock",
                product_id=pid,
                product_name=p_name,
                quantity=qty,
                unit=unit,
                unit_price=matched_prod.purchase_price if matched_prod else 0.0,
                expected_stock_balance=curr_stock + qty,
                explanation=f"{p_name} కు {qty} {unit} స్టాక్ జోడించబడుతుంది." if is_telugu else f"Adding {qty} {unit} to {p_name}.",
                raw_speech=text,
            )

        # Sale
        if any(w in lower for w in ["అమ్మాను", "అమ్మకం", "sold", "sale"]):
            return VoiceInterpretResponse(
                action_type="record_sale",
                product_id=pid,
                product_name=p_name,
                quantity=qty,
                unit=unit,
                unit_price=matched_prod.selling_price if matched_prod else 0.0,
                expected_stock_balance=max(0.0, curr_stock - qty),
                explanation=f"{p_name} నుండి {qty} {unit} అమ్మకం నమోదు చేయబడుతుంది." if is_telugu else f"Recording sale of {qty} {unit} for {p_name}.",
                raw_speech=text,
            )

        # Query Stock
        if any(w in lower for w in ["ఎన్ని", "ఉన్నాయి", "how many", "stock left"]):
            return VoiceInterpretResponse(
                action_type="check_stock",
                product_id=pid,
                product_name=p_name,
                quantity=curr_stock,
                unit=unit,
                explanation=f"{p_name} ప్రస్తుత నిల్వ: {curr_stock} {unit}." if is_telugu else f"Current stock of {p_name} is {curr_stock} {unit}.",
                raw_speech=text,
            )

        # Sales Query
        if any(w in lower for w in ["ఈరోజు అమ్మకాలు", "today's sales", "today sales"]):
            return VoiceInterpretResponse(
                action_type="check_sales",
                explanation="ఈరోజు మొత్తం అమ్మకాల వివరాలు నివేదికల్లో చూడవచ్చు." if is_telugu else "Today's sales summary is available in reports.",
                raw_speech=text,
            )

        return VoiceInterpretResponse(
            action_type="unknown",
            explanation="క్షమించండి, మీ మాట అర్థం కాలేదు. దయచేసి మళ్లీ చెప్పండి." if is_telugu else "Sorry, command was not recognized. Please try again.",
            raw_speech=text,
        )


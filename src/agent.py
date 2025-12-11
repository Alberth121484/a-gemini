import json
import structlog
from typing import Optional, List, Dict, Any
from datetime import datetime

import google.generativeai as genai

from .config import get_settings
from .database import ChatMemory, LogsManager, get_db_pool
from .tools import (
    CalculatorTool,
    WebSearchTool,
    ImageAnalysisTool,
    ImageGenerationTool,
    DocumentAnalysisTool,
    AudioTranscriber,
    AudioGenerator,
)

logger = structlog.get_logger()
settings = get_settings()

SYSTEM_PROMPT = """Rol
Eres un agente de IA multifuncional especializado en:
✅ Análisis de imágenes/documentos
✅ Generación de imágenes
✅ Cálculos matemáticos
✅ Búsqueda web
✅ Revisión lógica y verificación de datos

Fecha y hora actual: {current_time}

Estilo de respuesta:
- Lenguaje: Natural, claro y conciso.
- Tono: Profesional pero cercano.
- Prioridad: Precisión > Velocidad. Verifica siempre antes de responder.

Herramientas disponibles:
1. **calculator** - Para cálculos matemáticos
2. **web_search** - Para buscar información en internet
3. **image_analysis** - Para analizar imágenes
4. **image_generation** - Para crear imágenes desde texto
5. **document_analysis** - Para procesar documentos (PDF, Word, Excel, etc.)

Reglas:
- Si el usuario envía un archivo PDF/Word/Excel → usa document_analysis
- Si el usuario envía una imagen → usa image_analysis
- Si piden generar una imagen → usa image_generation
- Si necesitas información actualizada → usa web_search
- Para cálculos → usa calculator

Siempre responde en español a menos que el usuario escriba en otro idioma."""


class GeminiAgent:
    """Main AI Agent using Google Gemini with function calling."""
    
    def __init__(self):
        genai.configure(api_key=settings.google_api_key)
        
        # Initialize tools
        self.calculator = CalculatorTool()
        self.web_search = WebSearchTool()
        self.image_analysis = ImageAnalysisTool()
        self.image_generation = ImageGenerationTool()
        self.document_analysis = DocumentAnalysisTool()
        self.audio_transcriber = AudioTranscriber()
        self.audio_generator = AudioGenerator()
        self.logs_manager = LogsManager()
        
        # Define function declarations for Gemini
        self.tools = [
            genai.protos.Tool(
                function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name="calculator",
                        description="Performs mathematical calculations. Use for any math operations.",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "expression": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="Mathematical expression to evaluate, e.g. '5+3*2' or 'sqrt(16)'"
                                )
                            },
                            required=["expression"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="web_search",
                        description="Searches the web for information. Use when you need current information.",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "query": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="Search query"
                                )
                            },
                            required=["query"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="image_analysis",
                        description="Analyzes an image and describes its content.",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "image_url": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="URL of the image to analyze"
                                ),
                                "prompt": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="Optional specific question about the image"
                                )
                            },
                            required=["image_url"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="image_generation",
                        description="Generates an image from a text description.",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "prompt": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="Detailed description of the image to generate"
                                )
                            },
                            required=["prompt"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="document_analysis",
                        description="Analyzes documents (PDF, Word, Excel, etc.) and extracts content.",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "file_url": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="URL of the document to analyze"
                                ),
                                "query": genai.protos.Schema(
                                    type=genai.protos.Type.STRING,
                                    description="Optional specific question about the document"
                                )
                            },
                            required=["file_url"]
                        )
                    ),
                ]
            )
        ]
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=f"models/{settings.default_model}",
            tools=self.tools,
            system_instruction=SYSTEM_PROMPT.format(
                current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ),
        )
    
    async def execute_function(self, function_call) -> str:
        """Execute a function call from the model."""
        name = function_call.name
        args = dict(function_call.args)
        
        logger.info("Executing function", name=name, args=args)
        
        try:
            if name == "calculator":
                return await self.calculator.execute(args["expression"])
            elif name == "web_search":
                return await self.web_search.execute(args["query"])
            elif name == "image_analysis":
                return await self.image_analysis.execute(
                    args["image_url"],
                    args.get("prompt", "Analiza esta imagen")
                )
            elif name == "image_generation":
                # Return special marker for image generation
                return f"__IMAGE_GENERATION__:{args['prompt']}"
            elif name == "document_analysis":
                return await self.document_analysis.execute(
                    args["file_url"],
                    args.get("query")
                )
            else:
                return f"Unknown function: {name}"
        except Exception as e:
            logger.error("Function execution error", name=name, error=str(e))
            return f"Error executing {name}: {str(e)}"
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        file_url: Optional[str] = None,
        file_type: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a user message and return the response.
        
        Returns:
            Dict with keys: text, image_bytes, audio_bytes, needs_audio_response
        """
        result = {
            "text": None,
            "image_bytes": None,
            "audio_bytes": None,
            "needs_audio_response": False,
        }
        
        try:
            # Log the request
            if username and email:
                await self.logs_manager.log_request(user_id, username, email)
            
            # Get chat history
            memory = ChatMemory(user_id)
            history = await memory.get_history()
            
            # Build conversation
            chat_history = []
            for msg in history:
                role = "user" if msg["role"] == "human" else "model"
                chat_history.append({"role": role, "parts": [msg["content"]]})
            
            # Start chat with history
            chat = self.model.start_chat(history=chat_history)
            
            # Build the current message
            current_message = message
            if file_url:
                if file_type and file_type.startswith("image/"):
                    current_message += f"\n\n[Imagen adjunta: {file_url}]"
                elif file_type:
                    current_message += f"\n\n[Archivo adjunto: {file_url}]"
            
            # Send message and handle function calls
            response = await chat.send_message_async(current_message)
            
            # Process function calls in a loop
            max_iterations = 5
            iteration = 0
            
            while response.candidates[0].content.parts and iteration < max_iterations:
                part = response.candidates[0].content.parts[0]
                
                if hasattr(part, 'function_call') and part.function_call.name:
                    # Execute function
                    function_result = await self.execute_function(part.function_call)
                    
                    # Check if it's an image generation request
                    if function_result.startswith("__IMAGE_GENERATION__:"):
                        prompt = function_result.replace("__IMAGE_GENERATION__:", "")
                        try:
                            image_bytes, mime_type = await self.image_generation.execute(prompt)
                            result["image_bytes"] = image_bytes
                            result["text"] = f"He generado la imagen: {prompt}"
                        except Exception as e:
                            result["text"] = f"Error al generar la imagen: {str(e)}"
                        break
                    
                    # Send function result back to model
                    response = await chat.send_message_async(
                        genai.protos.Content(
                            parts=[
                                genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=part.function_call.name,
                                        response={"result": function_result}
                                    )
                                )
                            ]
                        )
                    )
                    iteration += 1
                else:
                    # No more function calls, we have the final text
                    break
            
            # Get final text response
            if not result["text"]:
                result["text"] = response.text
            
            # Save to memory
            await memory.add_interaction(current_message, result["text"])
            
            return result
            
        except Exception as e:
            logger.error("Agent processing error", error=str(e), user_id=user_id)
            result["text"] = f"Lo siento, ocurrió un error: {str(e)}"
            return result
    
    async def process_audio_message(
        self,
        user_id: str,
        audio_url: str,
        username: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process an audio message - transcribe, process, and optionally generate audio response."""
        # Transcribe audio
        transcribed_text = await self.audio_transcriber.execute(audio_url)
        
        if transcribed_text.startswith("Error"):
            return {"text": transcribed_text, "audio_bytes": None, "needs_audio_response": False}
        
        # Process the transcribed text
        result = await self.process_message(
            user_id=user_id,
            message=transcribed_text,
            username=username,
            email=email,
        )
        
        # Generate audio response
        if result["text"]:
            try:
                audio_bytes = await self.audio_generator.execute(result["text"])
                result["audio_bytes"] = audio_bytes
                result["needs_audio_response"] = True
            except Exception as e:
                logger.error("Audio response generation failed", error=str(e))
        
        return result


# Singleton instance
_agent_instance: Optional[GeminiAgent] = None


def get_agent() -> GeminiAgent:
    """Get or create the agent singleton."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = GeminiAgent()
    return _agent_instance

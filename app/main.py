from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import json
import base64
from app.scraper import UltimateScraper
from app.llm_service import generate_faqs_text, generate_final_html
from app.utils import log_interaction, logger
from app.auth import verify_password, create_access_token, decode_token, get_password_hash
from app.database import create_db_and_tables, get_session, Prompt, Template, History, Session, select
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Init DB on startup
@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    # Migration Logic (Seed data if empty)
    with Session(from app.database import engine) as session: # Need import inside or adjust imports
        from app.database import engine
        with Session(engine) as session:
            # Seed Prompts
            if not session.exec(select(Prompt)).first():
                logger.info("Seeding Prompts from file...")
                if os.path.exists("prompts.json"):
                    try:
                        with open("prompts.json", "r", encoding="utf-8") as f:
                            data = json.load(f)
                            session.add(Prompt(key="claude", content=data.get("system_prompt_claude", "")))
                            session.add(Prompt(key="gemini", content=data.get("system_prompt_gemini", "")))
                            session.commit()
                    except: pass
            
            # Seed Templates
            if not session.exec(select(Template)).first():
                logger.info("Seeding Templates from files...")
                if os.path.exists("templates/code"):
                    import os
                    for f in os.listdir("templates/code"):
                        if f.endswith(".html"):
                            name = f.replace(".html", "").replace("_", " ").title()
                            # Read HTML
                            with open(f"templates/code/{f}", "r", encoding="utf-8") as hf:
                                html_content = hf.read()
                            
                            # Read Image
                            img_name = f.replace(".html", ".png")
                            img_path = f"templates/img/{img_name}"
                            img_data = b""
                            if os.path.exists(img_path):
                                with open(img_path, "rb") as imgf:
                                    img_data = imgf.read()
                            
                            session.add(Template(name=name, html_content=html_content, image_data=img_data))
                    session.commit()


# Auth Configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    if not payload:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = payload.get("sub")
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

# Models API
class GenerateRequest(BaseModel):
    keyword: str
    brief: str
    source_type: str # 'url' or 'text'
    source_content: str
    template_id: int # Changed from str to int ID

class GenerateResponse(BaseModel):
    html_content: str

class TemplateInfo(BaseModel):
    id: int
    name: str
    html_path: str = "" # Deprecated but keep for frontend compatibility (hack) or remove
    img_url: str # Using base64 data URI or Serve endpoint

class PromptsData(BaseModel):
    system_prompt_claude: str
    system_prompt_gemini: str

class HistoryItem(BaseModel):
    id: Optional[int]
    date: str
    inputs: dict
    result: Optional[str]

# Scraper instance
scraper = UltimateScraper()

# Login Endpoint
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    env_user = os.environ.get("APP_USER", "admin")
    env_pass = os.environ.get("APP_PASSWORD", "admin123")
    
    if form_data.username != env_user or form_data.password != env_pass:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/verify-token")
async def verify_token_endpoint(current_user: str = Depends(get_current_user)):
    return {"status": "valid", "user": current_user}


# API Endpoints for Prompts
@app.get("/api/prompts", response_model=PromptsData)
async def get_prompts(current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    p_claude = session.exec(select(Prompt).where(Prompt.key == "claude")).first()
    p_gemini = session.exec(select(Prompt).where(Prompt.key == "gemini")).first()
    
    return PromptsData(
        system_prompt_claude=p_claude.content if p_claude else "",
        system_prompt_gemini=p_gemini.content if p_gemini else ""
    )

@app.post("/api/prompts")
async def save_prompts(data: PromptsData, current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    # Upsert Claude
    p_claude = session.exec(select(Prompt).where(Prompt.key == "claude")).first()
    if not p_claude:
        p_claude = Prompt(key="claude", content=data.system_prompt_claude)
        session.add(p_claude)
    else:
        p_claude.content = data.system_prompt_claude
        session.add(p_claude)
        
    # Upsert Gemini
    p_gemini = session.exec(select(Prompt).where(Prompt.key == "gemini")).first()
    if not p_gemini:
        p_gemini = Prompt(key="gemini", content=data.system_prompt_gemini)
        session.add(p_gemini)
    else:
        p_gemini.content = data.system_prompt_gemini
        session.add(p_gemini)
    
    session.commit()
    return {"status": "success"}

# API Endpoints for Templates
@app.post("/api/templates")
async def create_template(
    html_content: str = Form(...),
    image: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    try:
        img_data = await image.read()
        # Default name
        name = "Nueva Plantilla" # Could ask user, but keeping simple
        
        # We try to parse name from html title if possible or just generic
        # Let's count existing
        count = len(session.exec(select(Template)).all())
        name = f"Plantilla {count + 1}"

        new_tmpl = Template(name=name, html_content=html_content, image_data=img_data)
        session.add(new_tmpl)
        session.commit()
        session.refresh(new_tmpl)
            
        return {"status": "success", "id": new_tmpl.id}
    except Exception as e:
        logger.error(f"Error creating template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: int, current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    tmpl = session.get(Template, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    session.delete(tmpl)
    session.commit()
    return {"status": "deleted"}

@app.get("/api/templates", response_model=List[TemplateInfo])
async def get_templates(current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    templates = session.exec(select(Template)).all()
    result = []
    
    for t in templates:
        # Create a URL endpoint to serve the image? 
        # Or just embed base64 for simplicity in frontend (it's robust for migration)
        # Assuming images are small previews (~50-100KB)
        img_b64 = base64.b64encode(t.image_data).decode('utf-8')
        img_src = f"data:image/png;base64,{img_b64}" # Assume png/jpeg irrelevant for display mostly
        
        result.append(TemplateInfo(
            id=t.id,
            name=t.name,
            html_path="", # No longer useful
            img_url=img_src
        ))
    return result

# Endpoint for History
@app.get("/api/history", response_model=List[HistoryItem])
async def get_history(current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    # Get history for user, ordered by date desc (using created_at_ts ideally)
    # For now we order by ID desc
    history = session.exec(select(History).where(History.user_id == current_user).order_by(History.id.desc())).all()
    
    res = []
    for h in history:
        try:
            inputs = json.loads(h.inputs_json)
        except:
            inputs = {}
        res.append(HistoryItem(
            id=h.id,
            date=h.date,
            inputs=inputs,
            result=h.result_html
        ))
    return res

@app.post("/api/history")
async def save_history(item: HistoryItem, current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    # We ignore item.id for creation usually, or handle update
    # Frontend sends an ID timestamp usually
    
    # Store
    new_h = History(
        user_id=current_user,
        date=item.date,
        keyword=item.inputs.get("keyword", ""),
        inputs_json=json.dumps(item.inputs),
        result_html=item.result,
        created_at_ts=int(item.id) if item.id else 0 # Use frontend TS or generated
    )
    session.add(new_h)
    session.commit()
    return {"status": "success", "id": new_h.id}

@app.delete("/api/history/{id}")
async def delete_history(id: int, current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    # We need to find by created_at_ts likely if frontend uses TS as ID, OR we change frontend to use DB ID.
    # Frontend logic: id is Date.now(). Let's assume we match that to created_at_ts OR we change frontend to use DB ID.
    # To be safest: let's try to find by ID (if we updated frontend) OR created_at_ts.
    # But wait, frontend sends "id" which is a timestamp.
    
    # Try finding by TS
    h = session.exec(select(History).where(History.user_id == current_user).where(History.created_at_ts == id)).first()
    if not h:
         # Try by DB ID just in case
        h = session.get(History, id)
    
    if h and h.user_id == current_user:
        session.delete(h)
        session.commit()
        return {"status": "deleted"}
    
    raise HTTPException(status_code=404, detail="Item not found")

@app.put("/api/history/{id}")
async def update_history_name(id: int, kw_wrapper: Dict[str, str], current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    # kw_wrapper = {"keyword": "new name"}
    # Match logic from delete
    h = session.exec(select(History).where(History.user_id == current_user).where(History.created_at_ts == id)).first()
    if not h:
        h = session.get(History, id)

    if h and h.user_id == current_user:
        h.keyword = kw_wrapper.get("keyword", h.keyword)
        # Update inputs json too to keep sync?
        try:
            inp = json.loads(h.inputs_json)
            inp["keyword"] = h.keyword
            h.inputs_json = json.dumps(inp)
        except: pass
        
        session.add(h)
        session.commit()
        return {"status": "updated"}
        
    raise HTTPException(status_code=404, detail="Item not found")


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_faqs(request: GenerateRequest, current_user: str = Depends(get_current_user), session: Session = Depends(get_session)):
    try:
        logger.info(f"Received generation request for keyword: {request.keyword}")
        
        # Step 1: Content Acquisition (Client logic or scrape)
        web_content = ""
        if request.source_type == "url":
            logger.info("Scraping URL...")
            scrape_result = scraper.scrape(request.source_content)
            if not scrape_result:
                raise HTTPException(status_code=400, detail="Failed to scrape URL or invalid content.")
            web_content = scrape_result.get("full_text", "")
            if not web_content:
                 raise HTTPException(status_code=400, detail="Scraped content is empty.")
        else:
            web_content = request.source_content
            
        if not web_content:
             raise HTTPException(status_code=400, detail="No content provided.")

        # Step 2: Generate FAQ Text (Claude)
        logger.info("Generating FAQ text with Claude...")
        faq_texts = generate_faqs_text(request.keyword, request.brief, web_content)
        
        # Step 3: Get Template from DB
        template = session.get(Template, request.template_id)
        if not template:
             raise HTTPException(status_code=404, detail="Template not found.")
             
        template_html = template.html_content
            
        # Step 4: Generate Final HTML (Gemini)
        logger.info("Merging with template using Gemini...")
        final_html = generate_final_html(template_html, faq_texts)
        
        return GenerateResponse(html_content=final_html)

    except Exception as e:
        logger.error(f"Error in generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Mount Static Files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root
from fastapi.responses import FileResponse
@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/login")
async def login_page():
    return FileResponse("static/login.html")

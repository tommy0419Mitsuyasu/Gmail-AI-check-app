from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import Session, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import shutil
from pathlib import Path
import tempfile
from fastapi.staticfiles import StaticFiles

# データベース接続
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# モデル定義
class Engineer(Base):
    __tablename__ = "engineers"
    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String)
    email: str = Column(String, unique=True, index=True)
    current_role: str = Column(String)
    location: str = Column(String)
    total_experience_years: float = Column(Float)
    skills = relationship("Skill", back_populates="engineer")

class Project(Base):
    __tablename__ = "projects"
    id: int = Column(Integer, primary_key=True, index=True)
    project_name: str = Column(String)
    client_name: str = Column(String)
    description: str = Column(String)
    location: str = Column(String)
    work_type: str = Column(String)
    start_date: datetime = Column(DateTime, default=datetime.utcnow)
    duration_months: int = Column(Integer)
    min_budget: int = Column(Integer)
    max_budget: int = Column(Integer)
    requirements = relationship("ProjectRequirement", back_populates="project")

class Skill(Base):
    __tablename__ = "skills"
    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String)
    level: str = Column(String)
    engineer_id: int = Column(Integer, ForeignKey("engineers.id"))
    engineer = relationship("Engineer", back_populates="skills")

class ProjectRequirement(Base):
    __tablename__ = "project_requirements"
    id: int = Column(Integer, primary_key=True, index=True)
    skill: str = Column(String)
    level: str = Column(String)
    weight: int = Column(Integer, default=1)
    project_id: int = Column(Integer, ForeignKey("projects.id"))
    project = relationship("Project", back_populates="requirements")

# テーブル作成
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPIアプリケーションの作成
app = FastAPI(title="SESエンジンマッチングAPI")

# アップロードディレクトリの作成
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Pydanticモデルの定義
class SkillBase(BaseModel):
    name: str
    level: str

class EngineerBase(BaseModel):
    name: str
    email: str
    current_role: Optional[str] = None
    location: Optional[str] = None
    total_experience_years: Optional[float] = None

class ProjectBase(BaseModel):
    project_name: str
    client_name: str
    description: Optional[str] = None
    location: Optional[str] = None
    work_type: Optional[str] = None
    duration_months: Optional[int] = None
    min_budget: Optional[int] = None
    max_budget: Optional[int] = None

class ProjectRequirementBase(BaseModel):
    skill: str
    level: str
    weight: int = 1

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データベースセッションの依存関係
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ヘルスチェックエンドポイント
@app.get("/")
async def root():
    return {"status": "healthy", "message": "SESエンジンマッチングAPIが動作中です"}

# エンジニア一覧取得
@app.get("/engineers/", response_model=List[Dict[str, Any]])
def list_engineers(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    engineers = db.query(Engineer).offset(skip).limit(limit).all()
    
    result = []
    for eng in engineers:
        eng_dict = {
            "id": eng.id,
            "name": eng.name,
            "email": eng.email,
            "current_role": eng.current_role,
            "location": eng.location,
            "total_experience_years": eng.total_experience_years,
            "skills": [{"name": s.name, "level": s.level} for s in eng.skills]
        }
        result.append(eng_dict)
    
    return result

# プロジェクト一覧取得
@app.get("/projects/", response_model=List[Dict[str, Any]])
def list_projects(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    projects = db.query(Project).offset(skip).limit(limit).all()
    
    result = []
    for proj in projects:
        proj_dict = {
            "id": proj.id,
            "project_name": proj.project_name,
            "client_name": proj.client_name,
            "description": proj.description,
            "location": proj.location,
            "work_type": proj.work_type,
            "start_date": proj.start_date.isoformat() if proj.start_date else None,
            "duration_months": proj.duration_months,
            "budget_range": f"{proj.min_budget:,} - {proj.max_budget:,}円" if proj.min_budget and proj.max_budget else "未設定"
        }
        result.append(proj_dict)
    
    return result

# プロジェクトのマッチング結果取得
@app.get("/matches/{project_id}")
def get_matches(project_id: int, db: Session = Depends(get_db)):
    # プロジェクトを取得
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="プロジェクトが見つかりません")
    
    # プロジェクトの要件を取得
    requirements = db.query(ProjectRequirement).filter(ProjectRequirement.project_id == project_id).all()
    
    # 全てのエンジニアを取得
    engineers = db.query(Engineer).all()
    
    # マッチングスコアを計算
    matches = []
    for engineer in engineers:
        score = 0
        matched_skills = []
        
        # エンジニアのスキルを辞書に変換（スキル名をキーに）
        engineer_skills = {s.name.lower(): s for s in engineer.skills}
        
        # 各要件に対してマッチングを実行
        for req in requirements:
            skill_name = req.skill.lower()
            if skill_name in engineer_skills:
                # スキルがマッチした場合、レベルに応じてスコアを加算
                eng_skill = engineer_skills[skill_name]
                level_score = {"beginner": 1, "intermediate": 2, "expert": 3}.get(eng_skill.level.lower(), 0)
                score += level_score * req.weight
                matched_skills.append({
                    "skill": req.skill,
                    "required_level": req.level,
                    "engineer_level": eng_skill.level,
                    "match": eng_skill.level.lower() == req.level.lower()
                })
        
        if score > 0:  # 1つでもマッチするスキルがある場合のみ追加
            matches.append({
                "engineer_id": engineer.id,
                "engineer_name": engineer.name,
                "current_role": engineer.current_role,
                "experience_years": engineer.total_experience_years,
                "location": engineer.location,
                "score": score,
                "matched_skills": matched_skills
            })
    
    # スコアの高い順にソート
    matches.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "project_id": project.id,
        "project_name": project.project_name,
        "matches": matches
    }

# データベースの状態を確認するエンドポイント
@app.get("/check-db")
def check_database(db: Session = Depends(get_db)):
    try:
        engineers_count = db.query(Engineer).count()
        projects_count = db.query(Project).count()
        skills_count = db.query(Skill).count()
        requirements_count = db.query(ProjectRequirement).count()
        
        return {
            "status": "connected",
            "tables": {
                "engineers": engineers_count,
                "projects": projects_count,
                "skills": skills_count,
                "project_requirements": requirements_count
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

def init_db():
    # テーブルを再作成
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    # セッションを作成
    db = SessionLocal()
    
    try:
        # サンプルエンジニアを追加
        engineer1 = Engineer(
            name="山田太郎",
            email="yamada@example.com",
            current_role="シニアエンジニア",
            location="東京",
            total_experience_years=8.5
        )
        
        engineer2 = Engineer(
            name="佐藤花子",
            email="sato@example.com",
            current_role="フロントエンドエンジニア",
            location="大阪",
            total_experience_years=5.0
        )
        
        db.add_all([engineer1, engineer2])
        db.commit()
        
        # スキルを追加
        skill1 = Skill(name="Python", level="expert", engineer=engineer1)
        skill2 = Skill(name="JavaScript", level="intermediate", engineer=engineer1)
        skill3 = Skill(name="React", level="expert", engineer=engineer2)
        skill4 = Skill(name="TypeScript", level="intermediate", engineer=engineer2)
        
        db.add_all([skill1, skill2, skill3, skill4])
        
        # プロジェクトを追加
        project = Project(
            project_name="ECサイト開発",
            client_name="株式会社ABC",
            description="大手小売業向けECサイトの開発",
            location="東京",
            work_type="リモート可",
            duration_months=6,
            min_budget=5000000,
            max_budget=8000000
        )
        
        db.add(project)
        db.commit()
        
        # プロジェクト要件を追加
        req1 = ProjectRequirement(skill="Python", level="expert", weight=3, project=project)
        req2 = ProjectRequirement(skill="JavaScript", level="intermediate", weight=2, project=project)
        req3 = ProjectRequirement(skill="React", level="intermediate", weight=2, project=project)
        
        db.add_all([req1, req2, req3])
        db.commit()
        
    except Exception as e:
        db.rollback()
        print(f"Error initializing database: {e}")
    finally:
        db.close()

# ファイルアップロード用のエンドポイント
@app.post("/upload/skillsheet/")
async def upload_skillsheet(
    file: UploadFile = File(...),
    engineer_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """スキルシートをアップロードしてスキルを抽出・保存する"""
    try:
        # ファイルを一時的に保存
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in ['.pdf', '.docx', '.doc']:
            raise HTTPException(status_code=400, detail="サポートされていないファイル形式です。PDFまたはWord文書をアップロードしてください。")
        
        # 一時ファイルに保存
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # ファイルタイプに応じてテキストを抽出
        text = ""
        if file_ext == '.pdf':
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
        elif file_ext in ['.docx', '.doc']:
            import docx2txt
            text = docx2txt.process(file_path)
        
        # ここでスキルを抽出（簡易的な例）
        skills = extract_skills_from_text(text)
        
        # エンジニアを取得
        engineer = db.query(Engineer).filter(Engineer.id == engineer_id).first()
        if not engineer:
            raise HTTPException(status_code=404, detail="エンジニアが見つかりません")
        
        # 既存のスキルを削除
        db.query(Skill).filter(Skill.engineer_id == engineer_id).delete()
        
        # 新しいスキルを追加
        for skill_name, level in skills.items():
            skill = Skill(name=skill_name, level=level, engineer_id=engineer_id)
            db.add(skill)
        
        db.commit()
        
        return {"message": "スキルシートが正常に処理されました", "skills": skills}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"スキルシートの処理中にエラーが発生しました: {str(e)}")
    finally:
        # 一時ファイルを削除
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

def extract_skills_from_text(text: str) -> Dict[str, str]:
    """テキストからスキルを抽出する（簡易的な実装）"""
    # ここでは簡単のため、特定のキーワードを検出するだけの実装とします
    # 実際には、より高度な自然言語処理や機械学習を使用することが望ましいです
    
    # スキルとレベルのマッピング（簡易的な例）
    skill_keywords = {
        'Python': 'advanced',
        'Java': 'intermediate',
        'JavaScript': 'intermediate',
        'SQL': 'advanced',
        'Docker': 'beginner',
        'AWS': 'intermediate',
        'React': 'beginner',
        'Django': 'intermediate',
        'FastAPI': 'intermediate',
        'Git': 'intermediate'
    }
    
    # テキスト内のスキルを検出
    detected_skills = {}
    for skill, level in skill_keywords.items():
        if skill.lower() in text.lower():
            detected_skills[skill] = level
    
    # 最低1つはスキルがあることを確認
    if not detected_skills:
        detected_skills = {"不明な技術": "beginner"}
    
    return detected_skills

# アプリケーション起動時にデータベースを初期化
init_db()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

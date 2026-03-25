from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime

# SQLiteデータベースの設定
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ベースモデル
Base = declarative_base()

# エンジニアとスキルの関連テーブル
engineer_skills = Table(
    'engineer_skills',
    Base.metadata,
    Column('engineer_id', Integer, ForeignKey('engineers.id')),
    Column('skill_id', Integer, ForeignKey('skills.id'))
)

class Engineer(Base):
    __tablename__ = "engineers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    total_experience_years = Column(Float)
    current_role = Column(String)
    desired_roles = Column(String)
    location = Column(String)
    willing_to_relocate = Column(Boolean)
    current_salary = Column(Float, nullable=True)
    expected_salary = Column(Float, nullable=True)
    availability = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # リレーションシップ
    skills = relationship("Skill", secondary=engineer_skills, back_populates="engineers")

class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    category = Column(String)
    experience_years = Column(Float)
    level = Column(String)  # beginner, intermediate, expert
    
    # リレーションシップ
    engineers = relationship("Engineer", secondary=engineer_skills, back_populates="skills")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    source_email_id = Column(String)
    project_name = Column(String)
    client_name = Column(String)
    description = Column(String)
    location = Column(String)
    work_type = Column(String)
    duration_months = Column(Integer, nullable=True)
    start_date = Column(DateTime, nullable=True)
    min_budget = Column(Float, nullable=True)
    max_budget = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ProjectRequirement(Base):
    __tablename__ = "project_requirements"
    
    id = Column(Integer, primary_key=True, index=True)
    skill = Column(String)
    level = Column(String)
    required = Column(Boolean, default=True)
    weight = Column(Float, default=1.0)
    project_id = Column(Integer, ForeignKey('projects.id'))

# データベースの初期化
def init_db():
    # テーブルを作成
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # 既存のデータをクリア
        db.query(ProjectRequirement).delete()
        db.query(Project).delete()
        db.query(Skill).delete()
        db.query(Engineer).delete()
        
        # スキルを作成
        skills = [
            Skill(name="Python", category="programming", experience_years=5.0, level="expert"),
            Skill(name="FastAPI", category="framework", experience_years=3.0, level="expert"),
            Skill(name="Docker", category="devops", experience_years=2.0, level="intermediate"),
            Skill(name="JavaScript", category="programming", experience_years=3.0, level="expert"),
            Skill(name="React", category="framework", experience_years=3.0, level="expert"),
            Skill(name="TypeScript", category="programming", experience_years=2.0, level="intermediate")
        ]
        
        db.add_all(skills)
        db.commit()
        
        # エンジニアを作成
        engineer1 = Engineer(
            name="山田太郎",
            email="yamada@example.com",
            total_experience_years=5.5,
            current_role="バックエンドエンジニア",
            desired_roles="テックリード, アーキテクト",
            location="東京都",
            willing_to_relocate=True,
            current_salary=8000000,
            expected_salary=10000000,
            availability="1_month"
        )
        engineer1.skills = [skills[0], skills[1], skills[2]]  # Python, FastAPI, Docker
        
        engineer2 = Engineer(
            name="佐藤花子",
            email="sato@example.com",
            total_experience_years=3.0,
            current_role="フロントエンドエンジニア",
            desired_roles="フロントエンドリード",
            location="大阪府",
            willing_to_relocate=False,
            current_salary=6500000,
            expected_salary=8000000,
            availability="immediate"
        )
        engineer2.skills = [skills[3], skills[4], skills[5]]  # JavaScript, React, TypeScript
        
        db.add_all([engineer1, engineer2])
        db.commit()
        
        # プロジェクトを作成
        project1 = Project(
            source_email_id="project1@example.com",
            project_name="ECサイト開発プロジェクト",
            client_name="株式会社ABC",
            description="大規模ECサイトのバックエンドAPI開発",
            location="東京都",
            work_type="リモート可",
            duration_months=12,
            start_date=datetime.now(),
            min_budget=10000000,
            max_budget=15000000
        )
        
        project2 = Project(
            source_email_id="project2@example.com",
            project_name="ヘルスケアアプリ開発",
            client_name="医療法人XYZ",
            description="Reactを使用したフロントエンド開発",
            location="大阪府",
            work_type="ハイブリッド",
            duration_months=6,
            start_date=datetime.now(),
            min_budget=5000000,
            max_budget=8000000
        )
        
        db.add_all([project1, project2])
        db.commit()
        
        # プロジェクト要件を追加
        requirements = [
            ProjectRequirement(skill="Python", level="expert", weight=1.0, project_id=project1.id),
            ProjectRequirement(skill="FastAPI", level="intermediate", weight=0.8, project_id=project1.id),
            ProjectRequirement(skill="Docker", level="beginner", weight=0.5, project_id=project1.id),
            ProjectRequirement(skill="JavaScript", level="expert", weight=1.0, project_id=project2.id),
            ProjectRequirement(skill="React", level="expert", weight=1.0, project_id=project2.id),
            ProjectRequirement(skill="TypeScript", level="intermediate", weight=0.7, project_id=project2.id)
        ]
        
        db.add_all(requirements)
        db.commit()
        
        print("✅ データベースの初期化が完了しました")
        print(f"✅ エンジニア: {db.query(Engineer).count()}件")
        print(f"✅ スキル: {db.query(Skill).count()}件")
        print(f"✅ プロジェクト: {db.query(Project).count()}件")
        print(f"✅ プロジェクト要件: {db.query(ProjectRequirement).count()}件")
        
    except Exception as e:
        db.rollback()
        print(f"❌ エラーが発生しました: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("データベースを初期化しています...")
    init_db()

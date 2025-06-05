from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.db_models import Engineer, Project, Skill, ProjectRequirement, Base
from datetime import datetime, timedelta

# SQLiteデータベースの設定
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
        
        # サンプルエンジニア
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
        
        db.add_all([engineer1, engineer2])
        db.commit()
        db.refresh(engineer1)
        db.refresh(engineer2)
        
        # スキルを追加
        skills = [
            Skill(
                name="Python", category="programming", 
                experience_years=5.0, level="expert", engineer_id=engineer1.id
            ),
            Skill(
                name="FastAPI", category="framework", 
                experience_years=3.0, level="expert", engineer_id=engineer1.id
            ),
            Skill(
                name="Docker", category="devops", 
                experience_years=2.0, level="intermediate", engineer_id=engineer1.id
            ),
            Skill(
                name="JavaScript", category="programming", 
                experience_years=3.0, level="expert", engineer_id=engineer2.id
            ),
            Skill(
                name="React", category="framework", 
                experience_years=3.0, level="expert", engineer_id=engineer2.id
            ),
            Skill(
                name="TypeScript", category="programming", 
                experience_years=2.0, level="intermediate", engineer_id=engineer2.id
            )
        ]
        
        db.add_all(skills)
        
        # プロジェクトを追加
        project1 = Project(
            source_email_id="project1@example.com",
            project_name="ECサイト開発プロジェクト",
            client_name="株式会社ABC",
            description="大規模ECサイトのバックエンドAPI開発",
            location="東京都",
            work_type="リモート可",
            duration_months=12,
            start_date=datetime.now() + timedelta(days=30),
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
            start_date=datetime.now() + timedelta(days=14),
            min_budget=5000000,
            max_budget=8000000
        )
        
        db.add_all([project1, project2])
        db.commit()
        db.refresh(project1)
        db.refresh(project2)
        
        # プロジェクト要件を追加
        requirements = [
            ProjectRequirement(
                skill="Python", level="expert", weight=1.0, project_id=project1.id
            ),
            ProjectRequirement(
                skill="FastAPI", level="intermediate", weight=0.8, project_id=project1.id
            ),
            ProjectRequirement(
                skill="Docker", level="beginner", weight=0.5, project_id=project1.id
            ),
            ProjectRequirement(
                skill="JavaScript", level="expert", weight=1.0, project_id=project2.id
            ),
            ProjectRequirement(
                skill="React", level="expert", weight=1.0, project_id=project2.id
            ),
            ProjectRequirement(
                skill="TypeScript", level="intermediate", weight=0.7, project_id=project2.id
            )
        ]
        
        db.add_all(requirements)
        db.commit()
        
        print("✅ サンプルデータの挿入が完了しました")
        
    except Exception as e:
        db.rollback()
        print(f"❌ エラーが発生しました: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("データベースの初期化を開始します...")
    init_db()
    print("処理が完了しました")

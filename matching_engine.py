"""
ハイブリッド案件マッチングエンジン（有料API不使用・完全ローカル処理）

旧エンジンの問題点:
  1. 完全一致1件で 0.7 + 0.2 + 0.1*ドメイン ≒ 0.9 となり、どの案件も「90%」に張り付いていた
  2. 'it' / 'st' / 'ai' / 'ml' などの短い別名が部分一致し、無関係な案件にスキルが付与されていた
  3. 'バックエンド' 'フルスタック' 等のエンジニアタイプ名が「必須スキル」として一致していた
  4. 人材紹介メール（要員・人材情報）も案件として扱われていた
  5. メールが署名・ヘッダ単位に断片化され、文脈（必須/尚可）が失われていた

新エンジンの設計:
  - メール単位（複数案件メールは案件ごと）に「必須 / 尚可 / 環境 / 件名」のセクションを解析
  - 単語境界を厳密に扱うスキル辞書で抽出（Go / C / R などの曖昧語も文脈付きで判定）
  - IDF（希少度）重み: 'Go' のような希少スキルは重く、'Git' 'テスト' のような汎用スキルは軽く
  - スコア = 充足率^0.6 × 強み活用度^0.4 × 必須欠落ペナルティ × 根拠量係数
    * 充足率      : 案件が求めるスキルを候補者がどれだけ満たすか
    * 強み活用度  : 候補者の得意スキル（上位）が案件でどれだけ活きるか
    * 必須欠落    : 必須の言語/FWが無い場合は大幅減点
    * 根拠量係数  : 抽出スキルが少ない案件は確信度が低いので控えめに
"""
import re
import json
import math
import sqlite3
import logging
import threading
import unicodedata
from bisect import bisect_right
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# インデックスの仕様を変えたら上げる（自動で再構築される）
INDEX_VERSION = 4

# ---------------------------------------------------------------------------
# 1. スキル辞書
# ---------------------------------------------------------------------------
# 単語境界: 英数字に挟まれていないこと（右側は数字を許可: Java8, Python3 など）
_L = r'(?<![A-Za-z0-9])'
_R = r'(?![A-Za-z])'


def _w(*terms: str) -> str:
    """英字キーワードを単語境界付きの正規表現にする"""
    return _L + '(?:' + '|'.join(terms) + ')' + _R


# (正規名, カテゴリ, 親スキル, 正規表現, 高速プレフィルタ用の小文字トリガー語)
SKILL_DEFS: List[Tuple[str, str, Optional[str], str, Tuple[str, ...]]] = [
    # ===== プログラミング言語 =====
    ('Java', 'language', None, _w(r'java') + r'(?!\s*script)', ('java',)),
    ('JavaScript', 'language', None, _w(r'javascript', r'java\s+script', r'ecmascript', r'(?-i:JS)'), ('javascript', 'java script', 'js', 'ecmascript')),
    ('TypeScript', 'language', 'JavaScript', _w(r'typescript'), ('typescript',)),
    ('Python', 'language', None, _w(r'python'), ('python',)),
    ('Go', 'language', None, _L + r'(?:(?-i:Go)(?![A-Za-z])|golang|go言語)', ('go',)),
    ('PHP', 'language', None, _w(r'php'), ('php',)),
    ('Ruby', 'language', None, _w(r'ruby'), ('ruby',)),
    ('Kotlin', 'language', None, _w(r'kotlin'), ('kotlin',)),
    ('Swift', 'language', None, _w(r'swift', r'swiftui'), ('swift',)),
    ('Scala', 'language', None, _w(r'scala'), ('scala',)),
    ('Rust', 'language', None, _w(r'rust'), ('rust',)),
    ('Dart', 'language', None, _w(r'dart'), ('dart',)),
    ('Perl', 'language', None, _w(r'perl'), ('perl',)),
    ('Objective-C', 'language', None, _w(r'objective-c', r'objc'), ('objective', 'objc')),
    ('C#', 'language', None, _L + r'(?:c#|c♯|csharp)', ('c#', 'c♯', 'csharp')),
    ('C++', 'language', None, r'(?<![A-Za-z0-9])(?:vc\+\+|c\+\+|cpp)(?![A-Za-z])', ('c++', 'cpp')),
    # C 言語は誤検知が多いので「C言語」「C/C++」「C、」など区切り文字が続く場合のみ
    ('C', 'language', None, r'(?<![A-Za-z0-9\-#])(?-i:C)(?:言語|(?=\s*[/,、・)）\]】|]|\s*$))', ('c',)),
    ('R', 'language', None, r'(?<![A-Za-z0-9])(?-i:R)言語', ('r言語',)),
    ('VB.NET', 'language', None, _w(r'vb\.net'), ('vb.net',)),
    ('VB', 'language', None, r'(?<![A-Za-z0-9])(?:(?-i:VB)(?![A-Za-z.])|visual\s*basic|vb6)', ('vb', 'visual')),
    ('VBA', 'language', None, _w(r'vba') + r'|(?:excel|エクセル)\s*マクロ', ('vba', 'マクロ')),
    ('COBOL', 'language', None, _w(r'cobol'), ('cobol',)),
    ('PL/SQL', 'language', 'SQL', _w(r'pl/sql'), ('pl/sql',)),
    ('SQL', 'language', None, _w(r'sql'), ('sql',)),
    ('PowerShell', 'language', None, _w(r'powershell'), ('powershell',)),
    ('Shell', 'language', None, _w(r'shell', r'bash') + r'|シェル\s*スクリプト', ('shell', 'bash', 'シェル')),
    ('HTML', 'language', None, _w(r'html'), ('html',)),
    ('CSS', 'language', None, _w(r'css', r'scss', r'sass'), ('css', 'sass')),
    ('ABAP', 'language', 'SAP', _w(r'abap'), ('abap',)),
    ('Assembly', 'language', None, r'アセンブラ|アセンブリ|' + _w(r'assembler', r'assembly'), ('アセンブ', 'assembl')),

    # ===== フレームワーク / ライブラリ =====
    ('Spring', 'framework', 'Java', _w(r'spring\s*boot', r'springboot', r'spring\s*framework', r'spring'), ('spring',)),
    ('Struts', 'framework', 'Java', _w(r'struts'), ('struts',)),
    ('MyBatis', 'framework', 'Java', _w(r'mybatis', r'ibatis'), ('batis',)),
    ('Hibernate', 'framework', 'Java', _w(r'hibernate'), ('hibernate',)),
    ('JSP/Servlet', 'framework', 'Java', _w(r'jsp', r'servlet'), ('jsp', 'servlet')),
    ('Laravel', 'framework', 'PHP', _w(r'laravel'), ('laravel',)),
    ('CakePHP', 'framework', 'PHP', _w(r'cakephp'), ('cakephp',)),
    ('Symfony', 'framework', 'PHP', _w(r'symfony'), ('symfony',)),
    ('CodeIgniter', 'framework', 'PHP', _w(r'codeigniter'), ('codeigniter',)),
    ('FuelPHP', 'framework', 'PHP', _w(r'fuelphp'), ('fuelphp',)),
    ('Ruby on Rails', 'framework', 'Ruby', _w(r'ruby\s*on\s*rails', r'rails', r'ror'), ('rails', 'ror')),
    ('Django', 'framework', 'Python', _w(r'django'), ('django',)),
    ('Flask', 'framework', 'Python', _w(r'flask'), ('flask',)),
    ('FastAPI', 'framework', 'Python', _w(r'fastapi'), ('fastapi',)),
    ('Gin', 'framework', 'Go', r'(?<![A-Za-z0-9])(?-i:Gin)(?![A-Za-z])', ('gin',)),
    ('Echo', 'framework', 'Go', r'(?<![A-Za-z0-9])(?-i:Echo)(?![A-Za-z])', ('echo',)),
    ('.NET', 'framework', 'C#', r'(?<![A-Za-z0-9])(?:asp\.net(?:\s*core)?|\.net(?:\s*(?:core|framework))?|dotnet)(?![A-Za-z])', ('.net', 'dotnet')),
    ('React Native', 'framework', 'React', _w(r'react\s*native'), ('native',)),
    ('React', 'framework', 'JavaScript', _w(r'react(?:\.js|js)?') + r'(?!\s*native)', ('react',)),
    ('Next.js', 'framework', 'React', _w(r'next\.?js'), ('next',)),
    ('Vue.js', 'framework', 'JavaScript', _w(r'vue(?:\.js|js)?'), ('vue',)),
    ('Nuxt.js', 'framework', 'Vue.js', _w(r'nuxt(?:\.js|js)?'), ('nuxt',)),
    ('Angular', 'framework', 'TypeScript', _w(r'angular(?:\.js|js)?'), ('angular',)),
    ('jQuery', 'framework', 'JavaScript', _w(r'jquery'), ('jquery',)),
    ('Node.js', 'framework', 'JavaScript', _w(r'node\.?js', r'node'), ('node',)),
    ('NestJS', 'framework', 'TypeScript', _w(r'nest\.?js'), ('nest',)),
    ('Express', 'framework', 'Node.js', _w(r'express\.js', r'(?-i:Express)'), ('express',)),
    ('Flutter', 'framework', 'Dart', _w(r'flutter'), ('flutter',)),
    ('Android', 'framework', None, _w(r'android'), ('android',)),
    ('iOS', 'framework', None, r'(?<![A-Za-z0-9])(?-i:iOS)(?![A-Za-z])', ('ios',)),
    ('Unity', 'framework', 'C#', _w(r'unity'), ('unity',)),
    ('Unreal Engine', 'framework', 'C++', _w(r'unreal(?:\s*engine)?', r'ue[45]'), ('unreal', 'ue4', 'ue5')),
    ('Pandas', 'framework', 'Python', _w(r'pandas'), ('pandas',)),
    ('NumPy', 'framework', 'Python', _w(r'numpy'), ('numpy',)),
    ('PyTorch', 'framework', 'Python', _w(r'pytorch'), ('pytorch',)),
    ('TensorFlow', 'framework', 'Python', _w(r'tensorflow'), ('tensorflow',)),
    ('scikit-learn', 'framework', 'Python', _w(r'scikit-learn', r'sklearn'), ('scikit', 'sklearn')),
    ('機械学習', 'domain', None, r'機械学習|ディープラーニング|深層学習|' + _w(r'machine\s*learning', r'deep\s*learning'), ('機械学習', 'ディープ', '深層', 'learning')),
    ('生成AI/LLM', 'domain', None, r'生成\s*AI|生成AI|' + _w(r'llm', r'chatgpt', r'openai', r'gpt-?4o?', r'langchain', r'dify', r'(?-i:RAG)'), ('生成', 'llm', 'gpt', 'openai', 'langchain', 'dify', 'rag')),
    ('Salesforce', 'platform', None, _w(r'salesforce', r'sfdc', r'apex'), ('salesforce', 'sfdc', 'apex')),
    ('SAP', 'platform', None, r'(?<![A-Za-z0-9])(?-i:SAP)(?![A-Za-z])|' + _w(r's/4\s*hana', r'hana'), ('sap', 'hana')),
    ('ServiceNow', 'platform', None, _w(r'servicenow'), ('servicenow',)),
    ('kintone', 'platform', None, _w(r'kintone'), ('kintone',)),
    ('Power Platform', 'platform', None, _w(r'power\s*apps', r'power\s*automate', r'power\s*platform'), ('power',)),
    ('Power BI', 'platform', None, _w(r'power\s*bi'), ('power',)),
    ('Tableau', 'platform', None, _w(r'tableau'), ('tableau',)),
    ('RPA', 'platform', None, _w(r'uipath', r'winactor', r'rpa'), ('uipath', 'winactor', 'rpa')),

    # ===== データベース =====
    ('MySQL', 'database', None, _w(r'mysql', r'mariadb'), ('mysql', 'mariadb')),
    ('PostgreSQL', 'database', None, _w(r'postgres(?:ql)?', r'postgre') + r'|ポスグレ', ('postgre', 'ポスグレ')),
    ('Oracle', 'database', None, _w(r'oracle') + r'|オラクル', ('oracle', 'オラクル')),
    ('SQL Server', 'database', None, _w(r'sql\s*server', r'mssql'), ('server', 'mssql')),
    ('SQLite', 'database', None, _w(r'sqlite'), ('sqlite',)),
    ('MongoDB', 'database', None, _w(r'mongo(?:db)?'), ('mongo',)),
    ('Redis', 'database', None, _w(r'redis'), ('redis',)),
    ('DynamoDB', 'database', None, _w(r'dynamo(?:db)?'), ('dynamo',)),
    ('Elasticsearch', 'database', None, _w(r'elasticsearch', r'elastic\s*search', r'opensearch'), ('search',)),
    ('BigQuery', 'database', None, _w(r'bigquery', r'big\s*query'), ('query',)),
    ('Snowflake', 'database', None, _w(r'snowflake'), ('snowflake',)),
    ('Redshift', 'database', None, _w(r'redshift'), ('redshift',)),
    ('DB2', 'database', None, _w(r'db2'), ('db2',)),
    ('Access', 'database', None, r'(?<![A-Za-z0-9])(?-i:Access)(?![A-Za-z])', ('access',)),

    # ===== クラウド / インフラ =====
    ('AWS', 'cloud', None, _w(r'aws', r'amazon\s*web\s*services'), ('aws', 'amazon')),
    ('Azure', 'cloud', None, _w(r'azure'), ('azure',)),
    ('GCP', 'cloud', None, _w(r'gcp', r'google\s*cloud(?:\s*platform)?'), ('gcp', 'google')),
    ('Docker', 'infra', None, _w(r'docker'), ('docker',)),
    ('Kubernetes', 'infra', None, _w(r'kubernetes', r'k8s', r'eks', r'gke', r'aks', r'openshift'), ('kubernetes', 'k8s', 'eks', 'gke', 'aks', 'openshift')),
    ('Terraform', 'infra', None, _w(r'terraform'), ('terraform',)),
    ('Ansible', 'infra', None, _w(r'ansible'), ('ansible',)),
    ('CloudFormation', 'infra', 'AWS', _w(r'cloudformation', r'cdk'), ('cloudformation', 'cdk')),
    ('Linux', 'infra', None, _w(r'linux', r'rhel', r'red\s*hat', r'centos', r'ubuntu', r'almalinux'), ('linux', 'rhel', 'red', 'centos', 'ubuntu')),
    ('UNIX', 'infra', None, _w(r'unix', r'solaris', r'aix', r'hp-ux'), ('unix', 'solaris', 'aix', 'hp-ux')),
    ('Windows Server', 'infra', None, _w(r'windows\s*server') + r'|windowsサーバ', ('windows',)),
    ('Active Directory', 'infra', None, _w(r'active\s*directory', r'entra\s*id', r'azure\s*ad'), ('directory', 'entra', 'azure ad')),
    ('VMware', 'infra', None, _w(r'vmware', r'vsphere', r'esxi'), ('vmware', 'vsphere', 'esxi')),
    ('ネットワーク', 'infra', None, r'ネットワーク|' + _w(r'cisco', r'fortigate', r'palo\s*alto', r'ccna', r'ccnp', r'juniper', r'yamaha\s*rtx'), ('ネットワーク', 'cisco', 'fortigate', 'palo', 'ccna', 'ccnp', 'juniper', 'yamaha')),
    ('Zabbix', 'infra', None, _w(r'zabbix'), ('zabbix',)),
    ('Jenkins', 'infra', None, _w(r'jenkins'), ('jenkins',)),
    ('GitHub Actions', 'infra', None, _w(r'github\s*actions'), ('actions',)),
    ('CI/CD', 'infra', None, _w(r'ci/cd', r'cicd'), ('ci/cd', 'cicd')),
    ('Nginx', 'infra', None, _w(r'nginx'), ('nginx',)),
    ('Apache', 'infra', None, _w(r'apache') + r'(?!\s*(?:kafka|spark|airflow|hadoop))', ('apache',)),
    ('Tomcat', 'infra', None, _w(r'tomcat'), ('tomcat',)),
    ('Kafka', 'infra', None, _w(r'kafka'), ('kafka',)),
    ('Spark', 'infra', None, _w(r'spark', r'databricks'), ('spark', 'databricks')),
    ('Hadoop', 'infra', None, _w(r'hadoop'), ('hadoop',)),
    ('Airflow', 'infra', None, _w(r'airflow'), ('airflow',)),
    ('Datadog', 'infra', None, _w(r'datadog'), ('datadog',)),
    ('Intune/MDM', 'infra', None, _w(r'intune', r'mdm'), ('intune', 'mdm')),

    # ===== ツール =====
    ('Git', 'tool', None, _w(r'git'), ('git',)),
    ('GitHub', 'tool', None, _w(r'github'), ('github',)),
    ('GitLab', 'tool', None, _w(r'gitlab'), ('gitlab',)),
    ('SVN', 'tool', None, _w(r'svn', r'subversion'), ('svn', 'subversion')),
    ('Jira', 'tool', None, _w(r'jira'), ('jira',)),
    ('Confluence', 'tool', None, _w(r'confluence'), ('confluence',)),
    ('Backlog', 'tool', None, _w(r'(?-i:Backlog)'), ('backlog',)),
    ('Figma', 'tool', None, _w(r'figma'), ('figma',)),
    ('Photoshop', 'tool', None, _w(r'photoshop') + r'|フォトショ', ('photoshop', 'フォトショ')),
    ('Illustrator', 'tool', None, _w(r'illustrator') + r'|イラレ', ('illustrator', 'イラレ')),
    ('Excel', 'tool', None, _w(r'excel') + r'|エクセル', ('excel', 'エクセル')),
    ('Selenium', 'tool', None, _w(r'selenium'), ('selenium',)),
    ('JMeter', 'tool', None, _w(r'jmeter'), ('jmeter',)),
    ('Playwright', 'tool', None, _w(r'playwright'), ('playwright',)),
    ('Cypress', 'tool', None, _w(r'cypress'), ('cypress',)),
    ('JUnit', 'tool', 'Java', _w(r'junit'), ('junit',)),

    # ===== 工程 / 役割（重みは低め） =====
    ('要件定義', 'phase', None, r'要件定義', ('要件定義',)),
    ('基本設計', 'phase', None, r'基本設計|外部設計', ('基本設計', '外部設計')),
    ('詳細設計', 'phase', None, r'詳細設計|内部設計', ('詳細設計', '内部設計')),
    ('テスト', 'phase', None, r'テスト|試験|' + _w(r'qa'), ('テスト', '試験', 'qa')),
    ('運用保守', 'phase', None, r'運用保守|運用・保守|保守運用|運用|保守', ('運用', '保守')),
    ('PMO', 'role', None, r'(?<![A-Za-z0-9])(?-i:PMO)(?![A-Za-z])', ('pmo',)),
    ('PM', 'role', None, r'(?<![A-Za-z0-9])(?-i:PM)(?![A-Za-z])|プロジェクトマネージャ|プロジェクトマネジメント', ('pm', 'プロジェクトマネ')),
    ('PL', 'role', None, r'(?<![A-Za-z0-9])(?-i:PL)(?![A-Za-z/])|プロジェクトリーダ|チームリーダ|リーダー経験', ('pl', 'リーダ')),
    ('ヘルプデスク', 'role', None, r'ヘルプデスク|サービスデスク|サポートデスク|キッティング', ('ヘルプデスク', 'サービスデスク', 'サポートデスク', 'キッティング')),
]

SKILL_INFO: Dict[str, Dict] = {}
_COMPILED: List[Tuple[str, 're.Pattern', Tuple[str, ...]]] = []
for _name, _cat, _parent, _pat, _triggers in SKILL_DEFS:
    SKILL_INFO[_name] = {'category': _cat, 'parent': _parent}
    _COMPILED.append((_name, re.compile(_pat, re.IGNORECASE), _triggers))

# カテゴリごとの重要度（言語 > FW > クラウド > DB ...）
CATEGORY_WEIGHT = {
    'language': 1.0,
    'framework': 0.9,
    'platform': 0.9,
    'domain': 0.8,
    'cloud': 0.75,
    'infra': 0.65,
    'database': 0.6,
    'tool': 0.35,
    'role': 0.45,
    'phase': 0.25,
}
# 「強み」として扱わないカテゴリ
NON_CORE_CATEGORIES = {'phase', 'role', 'tool'}
# 必須欠落ペナルティの対象カテゴリ
HARD_CATEGORIES = {'language', 'framework', 'platform'}

# 相互に近いスキル（どちらを持っていても部分点）
_SIMILAR_PAIRS = {
    ('C', 'C++'): 0.6,
    ('C#', 'VB.NET'): 0.4,
    ('Java', 'Kotlin'): 0.45,
    ('Java', 'Scala'): 0.3,
    ('Swift', 'Objective-C'): 0.5,
    ('React', 'Vue.js'): 0.35,
    ('React', 'Angular'): 0.3,
    ('Vue.js', 'Angular'): 0.3,
    ('MySQL', 'PostgreSQL'): 0.6,
    ('MySQL', 'Oracle'): 0.5,
    ('MySQL', 'SQL Server'): 0.5,
    ('PostgreSQL', 'Oracle'): 0.5,
    ('PostgreSQL', 'SQL Server'): 0.5,
    ('Oracle', 'SQL Server'): 0.5,
    ('AWS', 'Azure'): 0.35,
    ('AWS', 'GCP'): 0.35,
    ('Azure', 'GCP'): 0.35,
    ('Git', 'GitHub'): 0.9,
    ('Git', 'GitLab'): 0.9,
    ('GitHub', 'GitLab'): 0.8,
    ('Docker', 'Kubernetes'): 0.5,
    ('Linux', 'UNIX'): 0.6,
    ('Shell', 'Linux'): 0.3,
    ('VB', 'VBA'): 0.5,
    ('VB', 'VB.NET'): 0.6,
    ('PM', 'PL'): 0.6,
    ('PM', 'PMO'): 0.6,
    ('PL', 'PMO'): 0.4,
    ('Terraform', 'CloudFormation'): 0.5,
    ('Jenkins', 'GitHub Actions'): 0.5,
    ('Jenkins', 'CI/CD'): 0.8,
    ('GitHub Actions', 'CI/CD'): 0.8,
    ('Android', 'Kotlin'): 0.6,
    ('iOS', 'Swift'): 0.6,
}
SIMILAR: Dict[Tuple[str, str], float] = {}
for (_a, _b), _v in _SIMILAR_PAIRS.items():
    SIMILAR[(_a, _b)] = _v
    SIMILAR[(_b, _a)] = _v

# 候補者側のスキル名 → 正規名（辞書の正規名以外の表記ゆれ）
_EXTRA_ALIASES = {
    'golang': 'Go', 'go言語': 'Go', 'go': 'Go',
    'c言語': 'C', 'c': 'C', 'r言語': 'R', 'r': 'R',
    'spring boot': 'Spring', 'springboot': 'Spring', 'spring framework': 'Spring',
    'vue': 'Vue.js', 'vuejs': 'Vue.js', 'react.js': 'React', 'reactjs': 'React',
    'nextjs': 'Next.js', 'nuxtjs': 'Nuxt.js', 'nodejs': 'Node.js', 'node': 'Node.js',
    'js': 'JavaScript', 'ts': 'TypeScript', 'postgres': 'PostgreSQL',
    'mssql': 'SQL Server', 'k8s': 'Kubernetes', 'rails': 'Ruby on Rails',
    'machine learning': '機械学習', 'deep learning': '機械学習', 'llm': '生成AI/LLM',
    'プロジェクトマネージャー': 'PM', 'プロジェクトリーダー': 'PL',
    'gitlab ci/cd': 'CI/CD', 'shell script': 'Shell', 'bash': 'Shell',
    'asp.net': '.NET', 'asp.net core': '.NET', 'dotnet': '.NET',
    'windows': 'Windows Server', 'subversion': 'SVN',
}
_CANONICAL_LOWER = {name.lower(): name for name in SKILL_INFO}


def extract_skill_positions(text: str) -> List[Tuple[str, int]]:
    """テキスト中のスキルを (正規名, 出現位置) のリストで返す"""
    if not text:
        return []
    lower = text.lower()
    found = []
    for name, pattern, triggers in _COMPILED:
        # 高速プレフィルタ: トリガー語が含まれない場合は正規表現を実行しない
        if not any(t in lower for t in triggers):
            continue
        for m in pattern.finditer(text):
            found.append((name, m.start()))
    return found


def canonicalize_skill_name(name: str) -> List[str]:
    """候補者のスキル名を正規名に変換する（該当なしは空リスト）"""
    if not name:
        return []
    raw = unicodedata.normalize('NFKC', str(name)).strip()
    key = raw.lower()
    if key in _CANONICAL_LOWER:
        return [_CANONICAL_LOWER[key]]
    if key in _EXTRA_ALIASES:
        return [_EXTRA_ALIASES[key]]
    # 'Java (5年)' のような表記にも対応するため正規表現抽出にフォールバック
    names = []
    for n, _ in extract_skill_positions(raw):
        if n not in names:
            names.append(n)
    return names


# ---------------------------------------------------------------------------
# 2. メール本文の構造解析
# ---------------------------------------------------------------------------
_NOISE_LINE = re.compile(r'(?:tel|fax|e-?mail|mail\s*[:：]|〒|https?://|www\.|@[A-Za-z0-9\-]+\.)', re.IGNORECASE)
_PROJECT_HEAD = re.compile(
    r'^\s*(?:\d+\s*[.)．]\s*)?[■◆●▼★☆◇□◎○▽▲*・\-]*\s*[【\[<＜(（〈《]?\s*'
    r'(?:案件名|案件\s*(?:no\.?|番号)?\s*[0-9①-⑳]+|案件\s*[:：]|件名\s*[:：])',
    re.IGNORECASE,
)
_SECTION_HEAD = re.compile(
    r'^\s*[■◆●▼★☆◇□◎○▽▲*・\-]*\s*[【\[<＜〈《(（]?\s*'
    r'([^】\]>＞〉》)）:：\s][^】\]>＞〉》)）:：]{0,18})\s*[】\]>＞〉》)）:：]\s*(.*)$'
)
_WANT_KW = ('尚可', '歓迎', 'あれば', '優遇', '望ましい', 'want', 'プラス', 'ベター', 'あると')
_MUST_KW = ('必須', '必要', '求める', '求む', '応募条件', 'must', 'スキル', '要件', '経験')
_META_KW = ('単価', '金額', '報酬', '勤務地', '場所', '最寄', '期間', '時期', '開始', '面談', '精算',
            '商流', '人数', '年齢', '国籍', '備考', '勤務時間', '支払', '契約', '稼働', 'リモート',
            '服装', '時間', '募集', '所属', '再委託', '貴社', '注意')

# セクション別の「案件にとっての重要度」
SECTION_WEIGHT = {'must': 1.0, 'title': 0.9, 'mixed': 0.75, 'desc': 0.6, 'want': 0.3, 'meta': 0.3}


def _classify_label(label: str) -> str:
    """見出しラベルをセクション種別に分類する"""
    lab = label.lower()
    has_want = any(k in lab for k in _WANT_KW)
    has_must = any(k in lab for k in ('必須', 'must', '必要'))
    if has_want and has_must:
        return 'mixed'
    if has_want:
        return 'want'
    if any(k in lab for k in _META_KW):
        return 'meta'
    if any(k in lab for k in _MUST_KW):
        return 'must'
    return 'desc'


def normalize_body(body: str) -> List[str]:
    """本文を正規化して行リストにする（署名・引用行は空行に置換して行番号を維持）"""
    text = unicodedata.normalize('NFKC', body or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('>') or _NOISE_LINE.search(s):
            lines.append('')
        else:
            lines.append(line)
    return lines


def split_units(lines: List[str]) -> List[Tuple[int, int]]:
    """1通のメールを案件単位の行範囲 [(start, end), ...] に分割する"""
    heads = [i for i, line in enumerate(lines) if _PROJECT_HEAD.match(line)]
    if len(heads) < 2:
        return [(0, len(lines))]
    ranges = []
    for idx, start in enumerate(heads):
        end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        ranges.append((start, end))
    return ranges


def analyze_unit(lines: List[str], subject: str) -> Dict:
    """案件単位のテキストを解析し、セクション付きスキル・タイトル・単価等を返す"""
    section = 'desc'
    skills: Dict[str, Dict] = {}
    title, price, location = '', '', ''

    def add(name: str, sec: str):
        w = SECTION_WEIGHT[sec]
        cur = skills.get(name)
        if cur is None:
            skills[name] = {'w': w, 'must': sec == 'must', 'secs': {sec}}
        else:
            cur['w'] = max(cur['w'], w)
            cur['must'] = cur['must'] or sec == 'must'
            cur['secs'].add(sec)

    pending_title = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        content = stripped
        m = _SECTION_HEAD.match(stripped)
        if m:
            label, rest = m.group(1).strip(), m.group(2).strip()
            section = _classify_label(label)
            content = rest
            if '案件名' in label or label in ('案件', '件名'):
                section = 'title'
                if rest:
                    title = title or rest[:80]
                else:
                    pending_title = True
            elif section == 'meta':
                if not price and any(k in label for k in ('単価', '金額', '報酬')):
                    price = rest[:60]
                if not location and any(k in label for k in ('勤務地', '場所', '最寄')):
                    location = rest[:60]
        elif len(stripped) <= 16 and any(k in stripped for k in _WANT_KW + ('必須',)):
            # 「必須スキル」のように記号なしで1行だけの見出し
            section = _classify_label(stripped)
            continue
        elif pending_title:
            title = stripped[:80]
            pending_title = False
        for name, _ in extract_skill_positions(content):
            add(name, section)
        if section == 'title':
            # 案件名の行は1行だけタイトル扱い、以降は概要として扱う
            section = 'desc'

    # 件名に含まれるスキルは中心スキルとみなす
    clean_subject = re.sub(r'^\s*(?:re|fw|fwd)\s*:\s*', '', subject or '', flags=re.IGNORECASE)
    clean_subject = re.sub(r'\[[a-z]+:\d+\]\s*', '', clean_subject, flags=re.IGNORECASE)
    for name, _ in extract_skill_positions(unicodedata.normalize('NFKC', clean_subject)):
        add(name, 'title')

    out_skills = {k: {'w': round(v['w'], 2), 'must': v['must'],
                      'want_only': v['secs'] == {'want'}} for k, v in skills.items()}
    return {'skills': out_skills, 'title': title or clean_subject.strip()[:100],
            'price': price, 'location': location}


# ---------------------------------------------------------------------------
# 3. メール種別判定（案件 / 人材紹介 / その他）
# ---------------------------------------------------------------------------
_SUBJ_PROJECT = re.compile(r'案件|募集|急募|求人|ポジション|交代枠|増員|求む|PJ|プロジェクト|JO-\d', re.IGNORECASE)
_SUBJ_PERSON = re.compile(
    r'人材|要員|技術者|のご紹介です|エンジニアのご紹介|直個人|フリーランス情報|弊社直フリーランス|'
    r'\d{2}\s*歳|スキルシート|稼働可能|プロパー|正社員.*紹介|個人事業主|弊社社員|所属社員|【直人材'
)
_SUBJ_OTHER = re.compile(r'請求書|退職|ご報告|お知らせ|障害|休業|セミナー|ウェビナー|勉強会|年末年始|夏季休暇|メルマガ')
_BODY_PERSON = ('年齢', '性別', '最寄駅', '最寄り駅', '稼働開始', '希望単価', '国籍', '氏名', 'イニシャル', '経験年数', '所属')
_BODY_PROJECT = ('必須', '尚可', '歓迎', '業務内容', '作業内容', '募集人数', '面談回数', '精算', '案件概要', '募集')

# 人材メールであることがほぼ確実な件名パターン（「案件」等の語が併記されていても人材と判定する）
#   例: 【プロパー人材情報】…案件探してます / 【弊社フリーランス】… / ●人材● … 39歳 / 【要員】PMO…
_SUBJ_PERSON_STRONG = re.compile(
    r'人[材財]\s*情報|技術者\s*情報|要員\s*情報|エンジニア\s*情報|'
    # 「【GFD人材】」「●人材●」「【要員】」のように見出しが人材/要員で終わるもの
    r'[【\[●■◆★<＜]\s*[^】\]●■◆★>＞]{0,12}(?:人[材財]|要員)\s*[!！]?\s*[】\]●■◆★>＞]|'
    r'(?:弊社|自社|当社)\s*(?:プロパー|フリーランス|社員|所属|個人事業主|要員|技術者|エンジニア|契約社員|BP)|'
    r'直\s*(?:フリーランス|個人|人材)|'
    # 人材側が案件を探している表現
    r'案件\s*(?:を|の)?\s*(?:探し|探して|お探し中|お待ち|募集中|希望|幅広|ください|下さい|頂けますと|いただけますと|'
    r'(?:ご)?紹介\s*(?:ください|下さい|頂け|いただけ|お願い))|'
    r'待機\s*(?:中|と\s*なり|に\s*なり)|'
    # 「24歳男性」「/ 33歳 /」のような本人の年齢（「45歳まで」「20〜45歳」などの案件条件は除外）
    r'(?<![~～〜\-－0-9])\d{2}\s*歳(?!\s*(?:まで|迄|以下|以内|未満|位|くらい|程度|前後|[~～〜\-－]))'
)
# 「要員募集」「技術者をお探し」「人材ご紹介お願い」のような “案件側が人を求める” 表現（人材判定から除外する）
_SUBJ_SEEK_PERSON = re.compile(
    r'(?:人[材財]|要員|技術者|エンジニア|経験者|方)\s*(?:を|の|が)?\s*'
    r'(?:募集|急募|求む|探して|お探し|ください|下さい|(?:ご)?紹介\s*(?:のお願い|お願い|依頼|ください|下さい)|ご提案)'
)


def classify_email(subject: str, body_head: str) -> str:
    subj = unicodedata.normalize('NFKC', subject or '')
    # 人材メール特有の強いシグナルがあれば、案件系の語が含まれていても人材として扱う
    if _SUBJ_PERSON_STRONG.search(subj):
        return 'person'
    is_proj = bool(_SUBJ_PROJECT.search(subj))
    # 「要員募集」等の “人を求める” 表現は人材判定の根拠にしない
    is_person = bool(_SUBJ_PERSON.search(_SUBJ_SEEK_PERSON.sub(' ', subj)))
    if is_proj and not is_person:
        return 'project'
    if is_person and not is_proj:
        return 'person'
    if not is_proj and not is_person and _SUBJ_OTHER.search(subj):
        return 'other'
    head = body_head[:1500]
    person_score = sum(head.count(k) for k in _BODY_PERSON)
    project_score = sum(head.count(k) for k in _BODY_PROJECT)
    if is_proj and is_person:
        return 'person' if person_score > project_score + 1 else 'project'
    if project_score >= 2 and project_score >= person_score:
        return 'project'
    if person_score >= 2:
        return 'person'
    return 'other'


# ---------------------------------------------------------------------------
# 4. インデックス（SQLite に永続化、差分更新）
# ---------------------------------------------------------------------------
class MatchingEngine:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from db_manager import db_manager
            db_path = db_manager.db_path
        self.db_path = db_path
        self._lock = threading.Lock()
        self._cache = None          # 案件ユニットのメモリキャッシュ
        self._cache_stamp = None    # キャッシュの鮮度判定用
        self._ensure_table()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        conn = self._conn()
        try:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS email_skill_index (
                message_id TEXT,
                unit_idx INTEGER,
                version INTEGER,
                kind TEXT,
                title TEXT,
                price TEXT,
                location TEXT,
                line_start INTEGER,
                line_end INTEGER,
                skills_json TEXT,
                PRIMARY KEY (message_id, unit_idx)
            )''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_esi_kind ON email_skill_index(kind)')
            conn.commit()
        finally:
            conn.close()

    def update_index(self, batch_size: int = 500) -> int:
        """未解析（またはバージョンが古い）メールを解析してインデックスに追加する"""
        with self._lock:
            conn = self._conn()
            processed = 0
            try:
                conn.execute('DELETE FROM email_skill_index WHERE version != ?', (INDEX_VERSION,))
                conn.commit()
                while True:
                    rows = conn.execute('''
                        SELECT e.message_id, e.subject, e.body FROM emails e
                        WHERE NOT EXISTS (SELECT 1 FROM email_skill_index i WHERE i.message_id = e.message_id)
                        LIMIT ?''', (batch_size,)).fetchall()
                    if not rows:
                        break
                    records = []
                    for r in rows:
                        records.extend(self._analyze_email(r['message_id'], r['subject'], r['body']))
                    conn.executemany('''
                        INSERT OR REPLACE INTO email_skill_index
                        (message_id, unit_idx, version, kind, title, price, location, line_start, line_end, skills_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', records)
                    conn.commit()
                    processed += len(rows)
                    logger.info(f"マッチング用インデックス更新中: {processed} 件")
            finally:
                conn.close()
            if processed:
                self._cache = None
            return processed

    def _analyze_email(self, message_id: str, subject: str, body: str) -> List[tuple]:
        lines = normalize_body(body)
        kind = classify_email(subject, '\n'.join(lines[:60]))
        records = []
        if kind == 'project':
            for idx, (start, end) in enumerate(split_units(lines)):
                info = analyze_unit(lines[start:end], subject)
                if not info['skills']:
                    continue
                records.append((message_id, idx, INDEX_VERSION, kind, info['title'], info['price'],
                                info['location'], start, end, json.dumps(info['skills'], ensure_ascii=False)))
        if not records:
            # 解析済みマーカー（再解析を防ぐ）
            records.append((message_id, -1, INDEX_VERSION, kind, '', '', '', 0, 0, '{}'))
        return records

    # ------------------------------------------------------------------
    def _load_units(self, days: int) -> Dict:
        conn = self._conn()
        try:
            stamp = conn.execute('SELECT COUNT(*), MAX(rowid) FROM email_skill_index').fetchone()
            stamp = (tuple(stamp), days)
            if self._cache is not None and self._cache_stamp == stamp:
                return self._cache
            threshold = (datetime.now() - timedelta(days=days)).isoformat()
            rows = conn.execute('''
                SELECT i.message_id, i.unit_idx, i.title, i.price, i.location, i.skills_json,
                       e.subject, e.sender, e.received_at
                FROM email_skill_index i JOIN emails e ON e.message_id = i.message_id
                WHERE i.kind = 'project' AND i.unit_idx >= 0 AND e.received_at >= ?
                ORDER BY e.received_at DESC''', (threshold,)).fetchall()
        finally:
            conn.close()

        units = []
        df = Counter()
        seen = set()
        for r in rows:
            skills = json.loads(r['skills_json'])
            # 同一案件の重複配信を除去（件名の正規化 + スキル集合）
            norm_subj = re.sub(r'\[[a-z]+:\d+\]|\s|re:|fw:', '', (r['subject'] or '').lower())
            key = (norm_subj, r['title'], frozenset(skills))
            if key in seen:
                continue
            seen.add(key)
            units.append({'message_id': r['message_id'], 'unit_idx': r['unit_idx'], 'title': r['title'],
                          'price': r['price'], 'location': r['location'], 'skills': skills,
                          'subject': r['subject'], 'sender': r['sender'], 'received_at': r['received_at']})
            df.update(skills.keys())

        n = max(len(units), 1)
        idf = {s: math.log((n + 1) / (c + 1)) for s, c in df.items()}
        self._cache = {'units': units, 'idf': idf, 'n': n}
        self._cache_stamp = stamp
        return self._cache

    @staticmethod
    def _idf_weight(idf: Dict[str, float], skill: str) -> float:
        """希少度重み（0.4〜1.6）: 希少なスキルほど一致/不一致の意味が大きい"""
        v = idf.get(skill, 4.0)
        return min(1.6, max(0.4, v / 2.5))

    @staticmethod
    def _relation(project_skill: str, cand_skill: str) -> float:
        """案件側スキルに対し、候補者のスキルがどれだけ代替になるか（0〜1）"""
        if project_skill == cand_skill:
            return 1.0
        p_parent = SKILL_INFO.get(project_skill, {}).get('parent')
        c_parent = SKILL_INFO.get(cand_skill, {}).get('parent')
        score = SIMILAR.get((project_skill, cand_skill), 0.0)
        if c_parent == project_skill:
            score = max(score, 0.85)   # 例: 案件=Java / 候補者=Spring → Java は書ける
        if p_parent == cand_skill:
            score = max(score, 0.5)    # 例: 案件=Spring / 候補者=Java → 習得は早い
        if p_parent and p_parent == c_parent:
            score = max(score, 0.35)   # 例: 案件=Laravel / 候補者=CakePHP
        return score

    # ------------------------------------------------------------------
    def build_candidate_profile(self, raw_skills: List) -> Dict[str, Dict]:
        """候補者スキル（API入力）を正規化し、経験年数を含むプロフィールにする"""
        profile: Dict[str, Dict] = {}
        for s in raw_skills or []:
            if isinstance(s, str):
                name, years, category = s, None, ''
            elif isinstance(s, dict):
                name = s.get('name') or s.get('skill') or s.get('skill_name') or ''
                years = s.get('experience_years', s.get('experience', s.get('years')))
                category = str(s.get('category', '') or s.get('type', ''))
            else:
                continue
            if category in ('engineer_types', 'engineer_type', 'soft'):
                continue
            try:
                years = float(years) if years not in (None, '') else None
            except (TypeError, ValueError):
                years = None
            for canon in canonicalize_skill_name(name):
                cur = profile.get(canon)
                if cur is None or (years or 0) > (cur['years'] or 0):
                    profile[canon] = {'years': years, 'raw': name}
        return profile

    def match(self, raw_skills: List, days: int = 60, limit: int = 100, min_score: float = 30.0, target_price: Optional[int] = None, max_price: Optional[int] = None) -> Dict:
        """候補者スキルに対して案件をスコアリングして返す"""
        self.update_index()
        cache = self._load_units(days)
        idf = cache['idf']
        profile = self.build_candidate_profile(raw_skills)
        if not profile:
            return {'matches': [], 'profile': {}, 'total_units': len(cache['units'])}

        # 候補者スキルの重み: カテゴリ × 希少度 × 経験年数
        cand_w = {}
        for s, info in profile.items():
            cat = SKILL_INFO.get(s, {}).get('category', 'tool')
            years = info['years']
            exp = 0.6 + 0.4 * min(years, 5) / 5 if years is not None else 0.8
            cand_w[s] = CATEGORY_WEIGHT.get(cat, 0.4) * self._idf_weight(idf, s) * exp
        core = [s for s in sorted(cand_w, key=cand_w.get, reverse=True)
                if SKILL_INFO.get(s, {}).get('category') not in NON_CORE_CATEGORIES][:6]
        if not core:
            core = sorted(cand_w, key=cand_w.get, reverse=True)[:6]
        core_denominator = sum(sorted((cand_w[s] for s in core), reverse=True)[:2]) or 1.0

        results = []
        for unit in cache['units']:
            if target_price or max_price:
                price_text = unit.get('price', '')
                if not price_text:
                    continue
                from skill_extractor import skill_extractor
                price_info = skill_extractor._extract_price(price_text)
                if not price_info:
                    continue
                
                project_max = price_info.get('max_price') or price_info.get('min_price', 0)
                
                # 下限のチェック（案件の最大単価が、希望する最低単価を下回っていたら弾く）
                if target_price and project_max < target_price:
                    continue
                
                # 上限のチェック（案件の最大単価が、設定した上限を超えていたら弾く）
                if max_price and project_max > max_price:
                    continue
            scored = self._score_unit(unit, profile, cand_w, core, core_denominator, idf)
            if scored and scored['match_percentage'] >= min_score:
                results.append(scored)

        results.sort(key=lambda x: (x['match_percentage'], x.get('received_at') or ''), reverse=True)
        return {
            'matches': results[:limit],
            'profile': {'skills': list(profile.keys()), 'core': core},
            'total_units': len(cache['units']),
            'matched_units': len(results),
        }

    def _score_unit(self, unit, profile, cand_w, core, core_denominator, idf) -> Optional[Dict]:
        skills = unit['skills']
        tech = [s for s in skills if SKILL_INFO.get(s, {}).get('category') not in ('phase',)]
        if not tech:
            return None

        # ---- 充足率: 案件が求めるスキルをどれだけ満たすか ----
        req_total, req_hit = 0.0, 0.0
        penalty = 1.0
        matched, related, missing_must, missing_other = [], [], [], []
        for s, meta in skills.items():
            cat = SKILL_INFO.get(s, {}).get('category', 'tool')
            r = meta['w'] * CATEGORY_WEIGHT.get(cat, 0.4) * self._idf_weight(idf, s)
            best, best_by = 0.0, None
            for c in profile:
                v = self._relation(s, c)
                if v > best:
                    best, best_by = v, c
            req_total += r
            req_hit += r * best
            if best >= 1.0:
                matched.append(s)
            elif best > 0:
                related.append({'skill': s, 'by': best_by, 'ratio': round(best, 2)})
            if meta['must'] and best < 1.0:
                if cat in HARD_CATEGORIES:
                    penalty *= 0.45 if best == 0 else (0.7 + 0.3 * best)
                elif cat in ('cloud', 'database', 'infra', 'domain'):
                    penalty *= 0.85 if best == 0 else 0.95
                if best == 0:
                    missing_must.append(s)
            elif best == 0 and not meta.get('want_only'):
                missing_other.append(s)
        coverage = req_hit / req_total if req_total else 0.0
        if coverage <= 0:
            return None

        # ---- 強み活用度: 候補者の得意スキルが案件で活きるか ----
        strength = 0.0
        for c in core:
            hit = 0.0
            if c in skills:
                hit = min(1.0, skills[c]['w'] / 0.9) if not skills[c].get('want_only') else 0.4
            else:
                for s, meta in skills.items():
                    v = self._relation(s, c) * 0.8
                    if v > 0:
                        hit = max(hit, v * min(1.0, meta['w'] / 0.9))
            strength += cand_w[c] * hit
        relevance = min(1.0, strength / core_denominator)
        if relevance <= 0:
            return None

        # ---- 根拠量係数: 技術スキルが少ない案件は確信度を下げる ----
        evidence = 0.6 + 0.4 * (1 - math.exp(-len(tech) / 2))
        penalty = max(penalty, 0.1)
        score = 100.0 * (coverage ** 0.6) * (relevance ** 0.4) * penalty * evidence

        reasons = []
        if matched:
            reasons.append(f"一致スキル: {', '.join(matched[:8])}")
        if related:
            reasons.append('近いスキルで代替可: ' + ', '.join(f"{x['skill']}←{x['by']}" for x in related[:5]))
        if missing_must:
            reasons.append(f"不足している必須スキル: {', '.join(missing_must[:6])}")
        reasons.append(f"スキル充足率 {coverage * 100:.0f}% / 強み活用度 {relevance * 100:.0f}%"
                       + (f" / 必須不足ペナルティ ×{penalty:.2f}" if penalty < 1 else ''))
        if len(tech) <= 2:
            reasons.append('案件メールから読み取れる技術情報が少ないため、スコアを控えめに算出')

        unit_id = f"{unit['message_id']}#{unit['unit_idx']}"
        return {
            'id': unit_id,
            'message_id': unit['message_id'],
            'unit_idx': unit['unit_idx'],
            'title': unit['title'] or unit['subject'],
            'subject': unit['subject'],
            'sender': unit['sender'],
            'received_at': unit['received_at'],
            'price_text': unit['price'],
            'location': unit['location'],
            'match_percentage': round(score, 1),
            'required_skills': sorted(skills, key=lambda s: -skills[s]['w']),
            'must_skills': [s for s, m in skills.items() if m['must']],
            'matched_skills': matched,
            'related_skills': related,
            'missing_must_skills': missing_must,
            'missing_skills': missing_other,
            'reasons': reasons,
            'match_details': {
                'coverage': round(coverage * 100, 1),
                'relevance': round(relevance * 100, 1),
                'penalty': round(penalty, 2),
                'evidence': round(evidence, 2),
            },
            'gmail_url': f"https://mail.google.com/mail/u/0/#all/{unit['message_id']}",
        }

    def get_unit_text(self, message_id: str, unit_idx: int) -> str:
        """案件ユニットの本文（表示用）を返す"""
        conn = self._conn()
        try:
            row = conn.execute('SELECT body FROM emails WHERE message_id = ?', (message_id,)).fetchone()
            idx = conn.execute('SELECT line_start, line_end FROM email_skill_index WHERE message_id = ? AND unit_idx = ?',
                               (message_id, unit_idx)).fetchone()
        finally:
            conn.close()
        if not row:
            return ''
        body = (row['body'] or '').replace('\r\n', '\n')
        if not idx or (idx['line_start'] == 0 and idx['line_end'] >= len(body.split('\n'))):
            return body
        return '\n'.join(body.split('\n')[idx['line_start']:idx['line_end']])

    def match_candidates(self, project_text: str, days: int = 60, limit: int = 100, min_score: float = 20.0, exclude_freelance: bool = False, exclude_b2b: bool = False) -> Dict:
        """案件テキストに対して候補者（人材）をスコアリングして返す"""
        # 1. 案件テキストから必須/尚可スキルなどを抽出
        from skill_extractor import skill_extractor
        project_info = skill_extractor.extract_project_info(project_text)
        req_must = project_info.get('must_skills', [])
        req_want = project_info.get('want_skills', [])
        req_all = req_must + req_want
        
        if not req_all:
            # 見出しベースで抽出できなかった場合は全体から抽出
            all_extracted = skill_extractor._extract_skills_from_text(project_text)
            req_must = all_extracted.get('must', [])
            req_want = all_extracted.get('want', [])
            req_all = req_must + req_want

        # 名寄せ（正規化）した案件要求スキル
        req_skills_canon = set()
        for s in req_all:
            for c in canonicalize_skill_name(s):
                req_skills_canon.add(c)
                
        if not req_skills_canon:
            return {'matches': [], 'requirements': [], 'total_candidates': 0, 'matched_candidates': 0}

        # 2. データベースから人材情報をロード
        conn = self._conn()
        conn.row_factory = sqlite3.Row
        try:
            threshold = (datetime.now() - timedelta(days=days)).isoformat()
            
            c_rows = conn.execute('''
                SELECT c.id, c.email_message_id, c.name_initials, c.age, c.gender,
                       c.nearest_station, c.start_date, c.min_price, c.max_price,
                       c.work_type, c.description,
                       e.subject, e.sender, e.received_at
                FROM candidates c
                JOIN emails e ON c.email_message_id = e.message_id
                WHERE e.received_at >= ?
                ORDER BY e.received_at DESC
            ''', (threshold,)).fetchall()
            
            if not c_rows:
                return {'matches': [], 'requirements': list(req_skills_canon), 'total_candidates': 0, 'matched_candidates': 0}
                
            candidate_ids = [str(r['id']) for r in c_rows]
            s_placeholders = ','.join('?' * len(candidate_ids))
            
            s_rows = conn.execute(f'''
                SELECT cs.candidate_id, s.name, cs.type
                FROM candidate_skills cs
                JOIN skills s ON cs.skill_id = s.id
                WHERE cs.candidate_id IN ({s_placeholders})
            ''', candidate_ids).fetchall()
            
            cand_skills = {}
            for r in s_rows:
                cid = r['candidate_id']
                if cid not in cand_skills:
                    cand_skills[cid] = []
                for c in canonicalize_skill_name(r['name']):
                    cand_skills[cid].append(c)
                    
        finally:
            conn.close()

        # 3. 各人材のスコアリング
        results = []
        for row in c_rows:
            cid = row['id']
            c_skills = set(cand_skills.get(cid, []))
            
            # 要求スキルと保有スキルの積集合
            hit_skills = req_skills_canon.intersection(c_skills)
            
            if not hit_skills:
                continue
                
            # 簡易スコア算出: マッチしたスキル数 / 要求スキル数
            match_percentage = (len(hit_skills) / len(req_skills_canon)) * 100.0
            
            # 追加評価: 単価マッチ (案件の上限単価 >= 人材の下限単価)
            project_max = project_info.get('max_price') or project_info.get('min_price')
            cand_min = row['min_price']
            
            if project_max and cand_min:
                if cand_min <= project_max:
                    match_percentage += 10.0 # 単価マッチボーナス
                else:
                    match_percentage -= 20.0 # 予算オーバーペナルティ
                    
            # フィルタリング機能 (フリーランス・他社所属の除外)
            desc_text = (row['description'] or '').lower()
            if exclude_freelance:
                if 'フリーランス' in desc_text or '個人事業主' in desc_text:
                    continue # 弾く
            if exclude_b2b:
                if '1社先' in desc_text or '一社先' in desc_text or 'bp' in desc_text or 'パートナー' in desc_text:
                    continue # 弾く

            # 追加評価: 勤務地・最寄駅の簡易エリアボーナス (+5点)
            area_dict = {
                '東京': ['東京', '新宿', '渋谷', '品川', '池袋', '秋葉原', '六本木', '五反田', '新橋', '恵比寿', '目黒', '代々木', '神田', '浜松町'],
                '神奈川': ['神奈川', '横浜', '川崎', '武蔵小杉', 'みなとみらい', '新横浜'],
                '埼玉': ['埼玉', '大宮', '浦和', '和光市'],
                '千葉': ['千葉', '幕張', '船橋', '柏'],
                '関西': ['大阪', '梅田', '新大阪', '三宮', '神戸', '京都'],
            }
            
            proj_loc = (project_info.get('location') or project_text).lower()
            cand_loc = (row['nearest_station'] or '') + ' ' + (row['work_type'] or '')
            
            # リモート一致
            if 'リモート' in proj_loc and 'リモート' in cand_loc:
                match_percentage += 5.0
            else:
                # エリア一致
                for area, keywords in area_dict.items():
                    if any(k in proj_loc for k in keywords) and any(k in cand_loc for k in keywords):
                        match_percentage += 5.0
                        break

            match_percentage = min(match_percentage, 100.0)
            match_percentage = max(match_percentage, 0.0)

            
            if match_percentage >= min_score:
                results.append({
                    'candidate_id': cid,
                    'message_id': row['email_message_id'],
                    'name_initials': row['name_initials'],
                    'age': row['age'],
                    'gender': row['gender'],
                    'nearest_station': row['nearest_station'],
                    'start_date': row['start_date'],
                    'min_price': row['min_price'],
                    'max_price': row['max_price'],
                    'work_type': row['work_type'],
                    'description': row['description'],
                    'subject': row['subject'],
                    'sender': row['sender'],
                    'received_at': row['received_at'],
                    'hit_skills': list(hit_skills),
                    'all_skills': list(c_skills),
                    'match_percentage': match_percentage,
                    'match_reasons': [f"案件が求める必須スキル（{len(req_skills_canon)}件）のうち、{len(hit_skills)}件（{', '.join(list(hit_skills)[:3])}等）がマッチしています。"]
                })
                
        # マッチ率降順、受信日降順でソート
        results.sort(key=lambda x: (x['match_percentage'], x['received_at']), reverse=True)
        
        return {
            'matches': results[:limit],
            'requirements': list(req_skills_canon),
            'total_candidates': len(c_rows),
            'matched_candidates': len(results)
        }


_engine: Optional[MatchingEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> MatchingEngine:
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = MatchingEngine()
        return _engine

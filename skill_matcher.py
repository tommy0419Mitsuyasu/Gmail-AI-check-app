import re
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class SkillMatch:
    skill: str
    matched_terms: List[str]
    confidence: float

class SkillMatcher:
    def __init__(self):
        # スキルカテゴリとそのエイリアスマッピング
        self.skill_categories = {
            'programming_languages': {
                'python': ['python', 'py', 'python3', 'python2'],
                'javascript': ['javascript', 'js', 'ecmascript', 'es6', 'es2015'],
                'typescript': ['typescript', 'ts'],
                'java': ['java', 'j2ee', 'j2se', 'j2me'],
                'csharp': ['c#', 'csharp', '.net'],
                'cpp': ['c++', 'cpp', 'c plus plus'],
                'php': ['php'],
                'ruby': ['ruby', 'rb'],
                'go': ['go', 'golang'],
                'swift': ['swift'],
                'kotlin': ['kotlin', 'kt'],
                'scala': ['scala'],
                'rust': ['rust'],
                'dart': ['dart'],
                'r': ['r', 'rlang'],
                'matlab': ['matlab'],
            },
            'frameworks': {
                'django': ['django'],
                'flask': ['flask'],
                'fastapi': ['fastapi'],
                'spring': ['spring', 'spring boot', 'spring framework'],
                'ruby on rails': ['rails', 'ruby on rails', 'ror'],
                'laravel': ['laravel'],
                'express': ['express', 'express.js'],
                'react': ['react', 'react.js', 'reactjs'],
                'vue': ['vue', 'vue.js', 'vuejs'],
                'angular': ['angular', 'angular.js', 'angularjs'],
                'nextjs': ['next', 'next.js', 'nextjs'],
                'nuxtjs': ['nuxt', 'nuxt.js', 'nuxtjs'],
                'svelte': ['svelte'],
                'tensorflow': ['tensorflow', 'tf'],
                'pytorch': ['pytorch', 'torch'],
                'keras': ['keras'],
            },
            'cloud': {
                'aws': ['aws', 'amazon web services'],
                'azure': ['azure', 'microsoft azure'],
                'gcp': ['gcp', 'google cloud', 'google cloud platform'],
                'docker': ['docker'],
                'kubernetes': ['kubernetes', 'k8s'],
                'terraform': ['terraform'],
                'ansible': ['ansible'],
                'jenkins': ['jenkins'],
                'github actions': ['github actions', 'gh actions'],
                'gitlab ci': ['gitlab ci', 'gitlab-ci'],
            },
            'databases': {
                'mysql': ['mysql'],
                'postgresql': ['postgresql', 'postgres', 'pg'],
                'mongodb': ['mongodb', 'mongo'],
                'redis': ['redis'],
                'oracle': ['oracle', 'oracle db', 'oracledb'],
                'sql server': ['sql server', 'mssql', 'microsoft sql server'],
                'sqlite': ['sqlite', 'sqlite3'],
                'dynamodb': ['dynamodb', 'dynamo db'],
                'cassandra': ['cassandra'],
                'elasticsearch': ['elasticsearch', 'elastic search', 'es'],
            },
            'methodologies': {
                'agile': ['agile', 'scrum', 'kanban'],
                'devops': ['devops'],
                'ci/cd': ['ci/cd', 'ci cd', 'continuous integration', 'continuous deployment'],
                'tdd': ['tdd', 'test driven development'],
                'bdd': ['bdd', 'behavior driven development'],
                'microservices': ['microservices', 'micro service', 'micro-service'],
                'rest': ['rest', 'restful'],
                'graphql': ['graphql', 'gql'],
                'grpc': ['grpc', 'gRPC'],
            }
        }
        
        # スキルの正規化マップを作成
        self.skill_normalization_map = {}
        self.skill_aliases = {}
        
        for category, skills in self.skill_categories.items():
            for skill, aliases in skills.items():
                self.skill_aliases[skill] = aliases
                for alias in aliases + [skill]:
                    self.skill_normalization_map[alias] = skill

    def normalize_skill(self, skill: str) -> str:
        """スキル名を正規化する"""
        return self.skill_normalization_map.get(skill.lower(), skill.lower())

    def extract_skills_from_text(self, text: str) -> Dict[str, SkillMatch]:
        """テキストからスキルを抽出する"""
        text_lower = text.lower()
        found_skills = {}
        
        # スキルを検索
        for category, skills in self.skill_categories.items():
            for skill, aliases in skills.items():
                # 正規表現パターンを作成（単語境界を考慮）
                patterns = [r'\b' + re.escape(alias) + r'\b' for alias in aliases + [skill]]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                    for match in matches:
                        matched_term = match.group(0).lower()
                        # 既に見つかっている場合は、より長いマッチを優先
                        if skill not in found_skills or len(matched_term) > len(found_skills[skill].matched_terms[0]):
                            # 信頼度を計算（完全一致は1.0、部分一致は0.8）
                            confidence = 1.0 if match.group(0) == skill else 0.8
                            found_skills[skill] = SkillMatch(
                                skill=skill,
                                matched_terms=[matched_term],
                                confidence=confidence
                            )
                        elif skill in found_skills:
                            # 既存のマッチに用語を追加
                            if matched_term not in found_skills[skill].matched_terms:
                                found_skills[skill].matched_terms.append(matched_term)
        
        return found_skills

    def calculate_skill_weight(self, skill: str, context: str) -> float:
        """スキルの重みを計算する"""
        # 基本重み
        weight = 1.0
        
        # コンテキストに応じた重み付け
        context_lower = context.lower()
        
        # 必須スキルとして言及されているか
        if re.search(rf'(必須|必要|要|must have|required).*{re.escape(skill)}', context_lower, re.IGNORECASE):
            weight *= 1.5
            
        # 優遇スキルとして言及されているか
        if re.search(rf'(優遇|歓迎|あればなお可|plus|preferred).*{re.escape(skill)}', context_lower, re.IGNORECASE):
            weight *= 1.2
            
        # 経験年数が指定されている場合
        exp_match = re.search(rf'{re.escape(skill)}.*?(\d+)[ 　]*(?:年|years?|y)', context_lower, re.IGNORECASE)
        if exp_match:
            years = int(exp_match.group(1))
            weight *= min(1.0 + (years * 0.1), 2.0)  # 1年ごとに0.1倍、最大2.0倍まで
            
        return weight

    def match_engineer_to_project(self, engineer_skills: List[Dict[str, any]], project_requirements: List[Dict[str, any]], project_context: str = "") -> Dict[str, any]:
        """エンジニアのスキルとプロジェクト要件をマッチングする"""
        # エンジニアのスキルを正規化
        engineer_skill_set = {}
        for skill in engineer_skills:
            skill_name = skill.get('name', '').lower()
            normalized = self.normalize_skill(skill_name)
            if normalized not in engineer_skill_set:
                engineer_skill_set[normalized] = {
                    'original_name': skill_name,
                    'level': skill.get('level', '').lower(),
                    'experience': float(skill.get('experience_years', 0) or 0)
                }
        
        # マッチング結果
        matches = []
        total_weight = 0
        matched_weight = 0
        
        # 各要件に対してマッチング
        for req in project_requirements:
            req_skill = req.get('skill', '').lower()
            req_level = req.get('level', '').lower()
            req_weight = float(req.get('weight', 1.0))
            
            # 要件のスキルを正規化
            normalized_req = self.normalize_skill(req_skill)
            
            # マッチしたスキルを探す
            matched = False
            match_score = 0.0
            best_match = None
            
            for eng_skill, eng_data in engineer_skill_set.items():
                # スキル名が完全一致またはエイリアスに含まれるか
                if eng_skill == normalized_req or eng_skill in self.skill_aliases.get(normalized_req, []):
                    # レベルのマッチング
                    level_score = 1.0
                    if req_level:
                        if 'junior' in req_level and 'senior' in eng_data['level']:
                            level_score = 1.2  # 上級者が初級者要件にマッチする場合はボーナス
                        elif 'senior' in req_level and 'junior' in eng_data['level']:
                            level_score = 0.7  # 初級者が上級者要件にマッチする場合は減点
                    
                    # 経験年数に基づくスコア
                    exp_score = min(eng_data['experience'] * 0.1, 1.0)  # 10年で最大1.0
                    
                    # 総合スコア
                    score = level_score * (0.7 + 0.3 * exp_score)  # レベルを70%、経験を30%の重み
                    
                    if score > match_score:
                        match_score = score
                        best_match = {
                            'required_skill': req_skill,
                            'matched_skill': eng_data['original_name'],
                            'level': eng_data['level'],
                            'experience': eng_data['experience'],
                            'score': score,
                            'weight': req_weight
                        }
                        matched = True
            
            if matched and best_match:
                # コンテキストに基づいて重みを調整
                context_weight = self.calculate_skill_weight(best_match['required_skill'], project_context)
                best_match['context_weight'] = context_weight
                best_match['weighted_score'] = best_match['score'] * context_weight * req_weight
                
                matches.append(best_match)
                matched_weight += req_weight * context_weight
                
            total_weight += req_weight
        
        # 総合マッチ率を計算
        match_ratio = matched_weight / total_weight if total_weight > 0 else 0
        
        return {
            'matches': matches,
            'total_weight': total_weight,
            'matched_weight': matched_weight,
            'match_ratio': match_ratio,
            'matched_skills': [m['required_skill'] for m in matches],
            'missed_skills': [req.get('skill', '') for req in project_requirements 
                           if req.get('skill', '').lower() not in [m['required_skill'].lower() for m in matches]]
        }

import os
import json
import re
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class ProfileParser:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE")
        )
        self.model = os.getenv("OPENAI_MODEL", "deepseek-v3-1-250821")
    
    def parse_user_profile(self, user_message: str, conversation_history: List[Dict] = None) -> Dict:
        print(f"conversation_history: {conversation_history}")
        # construct prompt
        prompt = self._build_parsing_prompt(user_message, conversation_history)
        
        try:
            # call LLM
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts user preferences from natural language for activity recommendations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            # parse response
            result = response.choices[0].message.content.strip()
            profile = self._parse_llm_response(result)
            
            return profile
            
        except Exception as e:
            print(f"Error parsing user profile: {e}")
            # 返回默认profile
            return self._get_default_profile()
    
    def _build_parsing_prompt(self, user_message: str, conversation_history: List[Dict] = None) -> str:
        """构建解析提示词"""
        
        context = ""
        if conversation_history:
            context = "Previous conversation:\n"
            for turn in conversation_history[-3:]:  # 只取最近3轮对话
                context += f"{turn['role']}: {turn['content']}\n"
            context += "\n"
        
        prompt = f"""
{context}Please analyze the following user message and extract their preferences for activity recommendations. Return ONLY a JSON object with the following structure:

{{
    "interests": ["list of interests mentioned"],
    "languages": ["list of preferred languages"],
    "time_slots": ["morning", "afternoon", "evening", "any"],
    "budget": number (budget amount, or null if not mentioned),
    "need_free": boolean (true if they want free activities),
    "location": "city or area name if mentioned",
    "sourcetypes": ["course", "event", "interest_group"] or null
}}

Extraction rules:
- interests: Extract hobbies, activities, or topics they're interested in (e.g., "tai chi", "yoga", "fitness", "music", "cooking", "art", "reading")
- languages: Extract language preferences (default to ["English"] if not mentioned)
- time_slots: Extract when they prefer activities (morning/afternoon/evening/any)
- budget: Extract budget amount in dollars, or null if not mentioned
- need_free: true if they specifically want free activities, false otherwise
- location: Extract city, area, or location if mentioned
- sourcetypes: Extract activity types if mentioned

Examples:
- "I like tai chi in the morning, budget 50, free if possible" → {{"interests": ["tai chi"], "time_slots": ["morning"], "budget": 50, "need_free": true}}
- "I want fitness activities in Singapore" → {{"interests": ["fitness"], "location": "Singapore"}}
- "Can you suggest free music events?" → {{"interests": ["music"], "need_free": true}}

User message: "{user_message}"

Return only the JSON object, no other text:
"""
        return prompt
    
    def _parse_llm_response(self, response: str) -> Dict:
        """解析LLM响应为profile字典"""
        try:
            # 尝试直接解析JSON
            profile = json.loads(response)
            # 验证和清理数据
            return self._validate_and_clean_profile(profile)
            
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    profile = json.loads(json_match.group())
                    return self._validate_and_clean_profile(profile)
                except json.JSONDecodeError:
                    pass
            
            print(f"Failed to parse LLM response as JSON: {response}")
            return self._get_default_profile()
    
    def _validate_and_clean_profile(self, profile: Dict) -> Dict:
        """验证和清理profile数据"""
        
        # 确保所有字段都存在并有正确的类型
        cleaned_profile = {
            "interests": self._clean_list(profile.get("interests", [])),
            "languages": self._clean_list(profile.get("languages", ["English"])),
            "time_slots": self._clean_time_slots(profile.get("time_slots", ["any"])),
            "budget": self._clean_budget(profile.get("budget")),
            "need_free": bool(profile.get("need_free", False)),
            "location": str(profile.get("location", "")).strip(),
            "sourcetypes": self._clean_sourcetypes(profile.get("sourcetypes"))
        }
        return cleaned_profile
    
    def _clean_list(self, value) -> List[str]:
        """清理列表字段"""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
    
    def _clean_time_slots(self, value) -> List[str]:
        """清理时间段字段"""
        if not isinstance(value, list):
            return ["any"]
        
        valid_slots = ["morning", "afternoon", "evening", "any"]
        cleaned = []
        for slot in value:
            slot_lower = str(slot).lower().strip()
            if slot_lower in valid_slots:
                cleaned.append(slot_lower)
        
        return cleaned if cleaned else ["any"]
    
    def _clean_budget(self, value) -> Optional[float]:
        """清理预算字段"""
        if value is None:
            return None
        
        try:
            # 提取数字
            numbers = re.findall(r'\d+\.?\d*', str(value))
            if numbers:
                return float(numbers[0])
        except (ValueError, TypeError):
            pass
        
        return None
    
    def _clean_sourcetypes(self, value) -> Optional[List[str]]:
        """清理活动类型字段"""
        if not value:
            return None
        
        if not isinstance(value, list):
            return None
        
        valid_types = ["course", "event", "interest_group"]
        cleaned = []
        for stype in value:
            stype_lower = str(stype).lower().strip()
            if stype_lower in valid_types:
                cleaned.append(stype_lower)
        
        return cleaned if cleaned else None
    
    def _get_default_profile(self) -> Dict:
        """获取默认profile"""
        return {
            "interests": [],
            "languages": ["English"],
            "time_slots": ["any"],
            "budget": None,
            "need_free": False,
            "location": "",
            "sourcetypes": None
        }
    
    def enhance_profile_with_location(self, profile: Dict) -> Dict:
        """使用位置信息增强profile（添加经纬度）"""
        location = profile.get("location", "").strip()
        print(f"[DEBUG enhance_profile_with_location] location='{location}'")
        print(f"[DEBUG enhance_profile_with_location] profile before: {profile}")
        
        # 检查location是否为空、None字符串或无效值
        if not location or location.lower() in ['none', 'null', '']:
            # 如果没有位置信息，不设置默认坐标，让用户选择
            print(f"[DEBUG enhance_profile_with_location] No valid location, returning profile as-is")
            return profile
        
        # 这里可以集成地理编码服务来获取经纬度
        # 暂时使用默认坐标
        print(f"[DEBUG enhance_profile_with_location] Valid location found, setting default coordinates")
        profile["lat"] = 1.3521  # 新加坡默认坐标
        profile["lon"] = 103.8198
        
        return profile
    
    def update_profile_with_map_location(self, profile: Dict, lat: float, lon: float) -> Dict:
        """使用地图选择的经纬度更新profile"""
        profile["lat"] = lat
        profile["lon"] = lon
        profile["location"] = f"Selected location ({lat:.4f}, {lon:.4f})"
        return profile

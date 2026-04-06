"""
Meta (Facebook/Instagram) Ads skills for Lipaira.
"""

import requests
from skills.registry import BaseSkill
from skills.base import get_integration_tokens


class MetaGetAdPerformanceSkill(BaseSkill):
    name = "meta_get_ad_performance"
    description = (
        "Get Facebook/Instagram ad performance. "
        "Returns spend, reach, clicks, and conversions "
        "for active campaigns. Use for marketing briefings."
    )
    required_integrations = ["meta_ads"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "meta_ads")
        if not tokens:
            return {"success": False, "error": "Meta Ads not connected"}
        
        try:
            # Get ad accounts
            accounts_req = requests.get(
                "https://graph.facebook.com/v18.0/me/adaccounts",
                params={"access_token": tokens["access_token"], "fields": "id,name"}
            ).json()
            
            accounts = accounts_req.get("data", [])
            if not accounts:
                return {"success": False, "error": "No ad accounts found"}
            
            account_id = accounts[0]["id"]
            date_preset = params.get("date_preset", "last_7d")
            
            # Get insights
            resp = requests.get(
                f"https://graph.facebook.com/v18.0/{account_id}/insights",
                params={
                    "access_token": tokens["access_token"],
                    "fields": "campaign_name,spend,reach,clicks,impressions,ctr",
                    "date_preset": date_preset,
                    "level": "campaign"
                }
            )
            
            if resp.ok:
                data = resp.json().get("data", [])
                return {
                    "success": True,
                    "period": date_preset,
                    "campaigns": data,
                    "total_spend": sum(float(d.get("spend", 0)) for d in data)
                }
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


class MetaGetCampaignsSkill(BaseSkill):
    name = "meta_get_campaigns"
    description = (
        "Get active Facebook/Instagram ad campaigns "
        "with status and budget information."
    )
    required_integrations = ["meta_ads"]
    
    def execute(self, params, user_id, business_id=None):
        tokens = get_integration_tokens(user_id, business_id, "meta_ads")
        if not tokens:
            return {"success": False, "error": "Meta Ads not connected"}
        
        try:
            accounts_req = requests.get(
                "https://graph.facebook.com/v18.0/me/adaccounts",
                params={"access_token": tokens["access_token"], "fields": "id"}
            ).json()
            
            accounts = accounts_req.get("data", [])
            if not accounts:
                return {"success": False, "error": "No ad accounts"}
            
            account_id = accounts[0]["id"]
            resp = requests.get(
                f"https://graph.facebook.com/v18.0/{account_id}/campaigns",
                params={
                    "access_token": tokens["access_token"],
                    "fields": "name,status,objective,daily_budget",
                    "effective_status": ["ACTIVE", "PAUSED"]
                }
            )
            
            if resp.ok:
                return {"success": True, "campaigns": resp.json().get("data", [])}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
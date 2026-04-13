"""Google Ads integration skills for Lipaira.

Provides skills for interacting with Google Ads API.
Uses existing Google OAuth connection and GOOGLE_ADS_DEVELOPER_TOKEN.

Key functions/classes:
    GoogleAdsGetCampaignsSkill: Fetches campaign performance metrics (clicks, impressions, cost, conversions)
"""

from skills.registry import BaseSkill


class GoogleAdsGetCampaignsSkill(BaseSkill):
    name = "google_ads_get_campaigns"
    description = (
        "Get Google Ads campaign performance including "
        "clicks, impressions, cost, and conversions."
    )
    required_integrations = ["google"]

    def execute(self, params, user_id, business_id=None):
        from db import get_integration_tokens
        import os

        tokens = get_integration_tokens(user_id, business_id, "google")
        if not tokens:
            return {"success": False, "error": "Google not connected"}

        # Check for developer token
        developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not developer_token:
            return {"success": False, "error": "Google Ads developer token not configured"}

        customer_id = tokens.get("metadata", {}).get("google_ads_customer_id")
        if not customer_id:
            return {
                "success": False,
                "error": "Google Ads customer ID not set. Add it to your profile settings."
            }

        try:
            from google.ads.googleads.client import GoogleAdsClient

            config = {
                "developer_token": developer_token,
                "refresh_token": tokens.get("refresh_token"),
                "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                "use_proto_plus": True
            }

            client = GoogleAdsClient.load_from_dict(config)
            ga_service = client.get_service("GoogleAdsService")

            query = """
                SELECT campaign.name, campaign.status,
                metrics.clicks, metrics.impressions,
                metrics.cost_micros, metrics.conversions
                FROM campaign
                WHERE segments.date DURING LAST_7_DAYS
                AND campaign.status = 'ENABLED'
                ORDER BY metrics.cost_micros DESC
                LIMIT 10
            """

            response = ga_service.search(customer_id=customer_id, query=query)

            campaigns = []
            for row in response:
                campaigns.append({
                    "name": row.campaign.name,
                    "clicks": row.metrics.clicks,
                    "impressions": row.metrics.impressions,
                    "cost": row.metrics.cost_micros / 1_000_000,
                    "conversions": row.metrics.conversions
                })

            return {
                "success": True,
                "campaigns": campaigns,
                "total_spend": sum(c["cost"] for c in campaigns)
            }

        except ImportError:
            return {"success": False, "error": "google-ads library not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}
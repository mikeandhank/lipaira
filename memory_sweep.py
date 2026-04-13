"""
Memory Sweep — integration context loader for Lipaira.
When a user connects a new integration (QuickBooks, Google, etc.), this module
triggers an async background sweep to extract historical data and build
immediate context for the operator. Prevents empty-state syndrome after OAuth.
"""
import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def trigger_sweep(user_id: str, provider: str):
    """Trigger a sweep for a provider. Called after OAuth connect."""
    import threading
    thread = threading.Thread(target=run_sweep, args=(user_id, provider), daemon=True)
    thread.start()
    logger.info(f"Sweep triggered for {user_id}/{provider}")


def run_sweep(user_id: str, provider: str):
    """Run the sweep for a specific provider."""
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    try:
        if provider == 'quickbooks':
            sweep_quickbooks(user_id)
        elif provider == 'google':
            sweep_google(user_id)
        elif provider == 'microsoft':
            sweep_microsoft(user_id)
        elif provider == 'zoom':
            sweep_zoom(user_id)
        elif provider == 'calendly':
            sweep_calendly(user_id)
        elif provider == 'meta_ads':
            sweep_meta_ads(user_id)
        elif provider == 'canva':
            sweep_canva(user_id)
        elif provider == 'trello':
            sweep_trello(user_id)
        elif provider == 'asana':
            sweep_asana(user_id)
        else:
            logger.warning(f"Unknown sweep provider: {provider}")
    except Exception as e:
        logger.error(f"Sweep failed for {user_id}/{provider}: {e}")


def sweep_quickbooks(user_id: str) -> int:
    
    """Learn business context from QuickBooks."""
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    import requests
    from providers import get_secret
    
    graph = get_memory_graph(user_id)
    count = 0
    
    # Get QB tokens from user record
    # TODO: Fetch from user record (quickbooks_access_token, etc.)
    access_token = None
    
    if not access_token:
        logger.warning(f"No QuickBooks token for {user_id}")
        return 0
    
    try:
        realm_id = _get_qb_realm_id(user_id)
        if not realm_id:
            return 0
        
        headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'}
        
        # Get top customers by balance
        customers = _qb_query(headers, realm_id, 
            "SELECT * FROM Customer WHERE Active = true ORDER BY Balance DESC MAXRESULTS 20")
        
        for customer in customers[:5]:
            balance = float(customer.get('Balance', 0))
            if balance > 0:
                graph.add_memory(
                    content=f"Client {customer['DisplayName']} — ${balance:.0f} outstanding",
                    memory_type="fact",
                    confidence=0.9,
                    source="quickbooks_sweep"
                )
                count += 1
        
        # Get outstanding invoices
        invoices = _qb_query(headers, realm_id,
            "SELECT * FROM Invoice WHERE Balance > '0' ORDER BY DueDate MAXRESULTS 10")
        
        if invoices:
            total = sum(float(i.get('Balance', 0)) for i in invoices)
            graph.add_memory(
                content=f"{len(invoices)} unpaid invoices totalling ${total:.0f}",
                memory_type="fact",
                confidence=0.95,
                source="quickbooks_sweep"
            )
            count += 1
        
        logger.info(f"QuickBooks sweep for {user_id}: {count} memories")
        
    except Exception as e:
        logger.warning(f"QB sweep failed: {e}")
    
    return count


def sweep_google(user_id: str) -> int:
    
    """Learn context from Google Calendar and Gmail."""
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    import requests
    import psycopg2
    
    graph = get_memory_graph(user_id)
    count = 0
    
    try:
        # Get Google token from DB
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError('DATABASE_URL is required')
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT google_access_token, google_refresh_token FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row[0]:
            logger.warning(f"No Google token for {user_id}")
            return 0
        
        access_token = row[0]
        refresh_token = row[1]
        
        # Get calendar events for last 30 days
        headers = {'Authorization': f'Bearer {access_token}'}
        
        now = datetime.utcnow()
        thirty_days_ago = (now - timedelta(days=30)).isoformat() + 'Z'
        
        cal_resp = requests.get(
            'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            headers=headers,
            params={
                'timeMin': thirty_days_ago,
                'maxResults': 100,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
        )
        
        if cal_resp.ok:
            events = cal_resp.json().get('items', [])
            
            # Find working hours
            hours = []
            for event in events:
                start = event.get('start', {})
                if 'dateTime' in start:
                    try:
                        dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                        if dt.hour:  # 6am-10pm
                            hours.append(dt.hour)
                    except:
                        pass
            
            if hours:
                common_hours = sorted(set(hours), key=lambda h: hours.count(h), reverse=True)[:2]
                if common_hours:
                    graph.add_memory(
                        content=f"Typically works {min(common_hours)}am-{max(common_hours)%12 or 12}pm",
                        memory_type="preference",
                        confidence=0.7,
                        source="google_sweep"
                    )
                    count += 1
        
        logger.info(f"Google sweep for {user_id}: {count} memories")
        
    except Exception as e:
        logger.warning(f"Google sweep failed: {e}")
    
    return count


def sweep_microsoft(user_id: str) -> int:
    
    """Learn context from Microsoft 365."""
    # Similar to Google sweep but for Microsoft Graph API
    return 0


def _qb_query(headers: dict, realm_id: str, query: str) -> list:
    """Execute QuickBooks query."""
    import requests
    
    base_url = f'https://quickbooks.api.intuit.com/v3/company/{realm_id}/query'
    resp = requests.get(base_url, headers=headers, params={'query': query})
    
    if resp.ok:
        data = resp.json()
        return data.get('QueryResponse', {}).get('Customer', [])
    return []


def _get_qb_realm_id(user_id: str) -> str:
    """Get user's QuickBooks realm ID from DB."""
    # TODO: Implement
    return None


def sweep_zoom(user_id: str) -> int:
    """Learn context from Zoom meetings."""
    from skills.zoom.meetings import ZoomGetMeetingsSkill
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    count = 0
    try:
        graph = get_memory_graph(user_id)
        result = ZoomGetMeetingsSkill().execute({}, user_id=user_id)
        meetings = result.get("meetings", [])
        
        if meetings:
            graph.add_memory(
                content=f"Uses Zoom — {len(meetings)} upcoming meetings",
                memory_type="fact",
                confidence=0.8,
                source="zoom_sweep"
            )
            count += 1
            logger.info(f"Zoom sweep for {user_id}: {count} memories")
    except Exception as e:
        logger.warning(f"Zoom sweep failed: {e}")
    return count


def sweep_calendly(user_id: str) -> int:
    """Learn context from Calendly."""
    from skills.calendly.scheduling import CalendlyGetEventTypesSkill
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    count = 0
    try:
        graph = get_memory_graph(user_id)
        result = CalendlyGetEventTypesSkill().execute({}, user_id=user_id)
        types = result.get("event_types", [])
        
        if types:
            names = [t["name"] for t in types[:5]]
            graph.add_memory(
                content=f"Calendly booking types: {', '.join(names)}",
                memory_type="fact",
                confidence=0.85,
                source="calendly_sweep"
            )
            count += 1
            logger.info(f"Calendly sweep for {user_id}: {count} memories")
    except Exception as e:
        logger.warning(f"Calendly sweep failed: {e}")
    return count


def sweep_meta_ads(user_id: str) -> int:
    """Learn context from Meta Ads."""
    from skills.meta.ads import MetaGetCampaignsSkill
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    count = 0
    try:
        graph = get_memory_graph(user_id)
        result = MetaGetCampaignsSkill().execute({}, user_id=user_id)
        campaigns = result.get("campaigns", [])
        
        if campaigns:
            active = [c for c in campaigns if c.get("status") == "ACTIVE"]
            graph.add_memory(
                content=f"{len(active)} active Meta ad campaigns",
                memory_type="fact",
                confidence=0.9,
                source="meta_ads_sweep"
            )
            count += 1
            logger.info(f"Meta Ads sweep for {user_id}: {count} memories")
    except Exception as e:
        logger.warning(f"Meta Ads sweep failed: {e}")
    return count


def sweep_canva(user_id: str) -> int:
    """Learn context from Canva."""
    from skills.canva.designs import CanvaGetDesignsSkill
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    count = 0
    try:
        graph = get_memory_graph(user_id)
        result = CanvaGetDesignsSkill().execute({"limit": 20}, user_id=user_id)
        designs = result.get("designs", [])
        
        if designs:
            titles = [d["title"] for d in designs[:5] if d.get("title")]
            graph.add_memory(
                content=f"Has {len(designs)} Canva designs including: {', '.join(titles)}",
                memory_type="fact",
                confidence=0.75,
                source="canva_sweep"
            )
            count += 1
            logger.info(f"Canva sweep for {user_id}: {count} memories")
    except Exception as e:
        logger.warning(f"Canva sweep failed: {e}")
    return count


def sweep_trello(user_id: str) -> int:
    """Learn context from Trello."""
    from skills.trello.boards import TrelloGetCardsSkill
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    count = 0
    try:
        graph = get_memory_graph(user_id)
        result = TrelloGetCardsSkill().execute({}, user_id=user_id)
        cards = result.get("cards", [])
        
        if cards:
            open_cards = [c for c in cards if not c.get("dueComplete")]
            graph.add_memory(
                content=f"{len(open_cards)} open Trello cards / jobs in progress",
                memory_type="fact",
                confidence=0.85,
                source="trello_sweep"
            )
            count += 1
            logger.info(f"Trello sweep for {user_id}: {count} memories")
    except Exception as e:
        logger.warning(f"Trello sweep failed: {e}")
    return count


def sweep_asana(user_id: str) -> int:
    """Learn context from Asana."""
    from skills.asana.tasks import AsanaGetTasksSkill
    from memory_graph import CumulativeMemoryGraph as get_memory_graph
    
    count = 0
    try:
        graph = get_memory_graph(user_id)
        result = AsanaGetTasksSkill().execute({}, user_id=user_id)
        tasks = result.get("tasks", [])
        
        if tasks:
            graph.add_memory(
                content=f"{len(tasks)} open Asana tasks assigned to me",
                memory_type="fact",
                confidence=0.85,
                source="asana_sweep"
            )
            count += 1
            logger.info(f"Asana sweep for {user_id}: {count} memories")
    except Exception as e:
        logger.warning(f"Asana sweep failed: {e}")
    return count
"""
Cumulative Memory Graph — PostgreSQL-backed knowledge graph for Lipaira.
Extracted from nexusos-v2 for containerized deployment. Stores entities, facts,
and relationships as nodes and edges in PostgreSQL. Provides MemoryNode and
CumulativeMemoryGraph classes for add/recall/traverse operations. No workspace
dependencies — runs standalone with a DATABASE_URL connection.
"""
import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryNode:
    """A single node in the memory graph"""
    
    def __init__(self, node_id: str, node_type: str, content: str, 
                 confidence: float = 1.0, source: str = None):
        self.id = node_id
        self.type = node_type
        self.content = content
        self.confidence = confidence
        self.source = source
        self.created_at = datetime.utcnow()
        self.last_accessed = datetime.utcnow()
        self.access_count = 0
        self.activation_count = 0
        
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "activation_count": self.activation_count
        }


class MemoryEdge:
    """A connection between two memory nodes"""
    
    def __init__(self, from_id: str, to_id: str, edge_type: str, weight: float = 1.0):
        self.from_id = from_id
        self.to_id = to_id
        self.type = edge_type
        self.weight = weight
        self.created_at = datetime.utcnow()


class CumulativeMemoryGraph:
    """
    THE MOAT - Cumulative Memory Graph (PostgreSQL)
    Persistent memory that compounds over time.
    """
    
    def __init__(self, user_id: str, db_url: str = None):
        self.user_id = user_id
        self.db_url = db_url or os.environ.get('DATABASE_URL')
        
        self.nodes: Dict[str, MemoryNode] = {}
        self.edges: List[MemoryEdge] = []
        
        self._init_db()
        self._load_memory()
        
        logger.info(f"CumulativeMemoryGraph initialized for user {user_id}")
        logger.info(f"Loaded {len(self.nodes)} memory nodes")
    
    def _get_conn(self):
        """Get PostgreSQL connection"""
        return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
    
    def _init_db(self):
        """Initialize PostgreSQL tables"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_nodes (
                id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                last_accessed TIMESTAMP DEFAULT NOW(),
                access_count INTEGER DEFAULT 0,
                activation_count INTEGER DEFAULT 0,
                PRIMARY KEY (id, user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_edges (
                from_id TEXT NOT NULL,
                to_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (from_id, to_id, user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW(),
                data TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_nodes_user 
            ON memory_nodes(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_edges_user 
            ON memory_edges(user_id)
        """)
        
        conn.commit()
        conn.close()
    
    def _load_memory(self):
        """Load memory from PostgreSQL"""
        conn = self._get_conn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT * FROM memory_nodes 
            WHERE user_id = %s
        """, (self.user_id,))
        
        for row in cursor.fetchall():
            node = MemoryNode(
                node_id=row['id'],
                node_type=row['node_type'],
                content=row['content'],
                confidence=row['confidence'],
                source=row['source']
            )
            node.created_at = row['created_at']
            node.last_accessed = row['last_accessed']
            node.access_count = row['access_count']
            node.activation_count = row['activation_count']
            self.nodes[node.id] = node
        
        cursor.execute("""
            SELECT * FROM memory_edges 
            WHERE user_id = %s
        """, (self.user_id,))
        
        for row in cursor.fetchall():
            edge = MemoryEdge(
                from_id=row['from_id'],
                to_id=row['to_id'],
                edge_type=row['edge_type'],
                weight=row['weight']
            )
            edge.created_at = row['created_at']
            self.edges.append(edge)
        
        conn.close()
    
    def _save_node(self, node: MemoryNode):
        """Persist a single node to PostgreSQL"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memory_nodes 
            (id, user_id, node_type, content, confidence, source, created_at, last_accessed, access_count, activation_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id, user_id) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                last_accessed = EXCLUDED.last_accessed,
                access_count = EXCLUDED.access_count,
                activation_count = EXCLUDED.activation_count
        """, (
            node.id, self.user_id, node.type, node.content, node.confidence, node.source,
            node.created_at, node.last_accessed, node.access_count, node.activation_count
        ))
        
        conn.commit()
        conn.close()
    
    def _save_edge(self, edge: MemoryEdge):
        """Persist a single edge to PostgreSQL"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memory_edges 
            (from_id, to_id, user_id, edge_type, weight, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (from_id, to_id, user_id) DO UPDATE SET
                weight = EXCLUDED.weight
        """, (
            edge.from_id, edge.to_id, self.user_id, edge.type, edge.weight,
            edge.created_at
        ))
        
        conn.commit()
        conn.close()
    
    def _generate_node_id(self, content: str) -> str:
        """Generate deterministic ID"""
        return hashlib.sha256(f"{self.user_id}:{content}".encode()).hexdigest()[:16]
    
    def add_memory(self, content: str, memory_type: str = "fact", 
                   confidence: float = 1.0, source: str = None) -> MemoryNode:
        """Add a new memory to the graph."""
        node_id = self._generate_node_id(content)
        
        if node_id in self.nodes:
            self.nodes[node_id].confidence = min(1.0, self.nodes[node_id].confidence + 0.1)
            self.nodes[node_id].activation_count += 1
            self._save_node(self.nodes[node_id])
            return self.nodes[node_id]
        
        node = MemoryNode(node_id, memory_type, content, confidence, source)
        self.nodes[node_id] = node
        self._save_node(node)
        self._connect_to_related(node)
        
        logger.info(f"Added memory: {memory_type} - {content[:50]}...")
        return node
    
    def _connect_to_related(self, new_node: MemoryNode):
        """Connect new memory to existing related memories"""
        for node_id, node in self.nodes.items():
            if node_id == new_node.id:
                continue
            
            common_words = set(new_node.content.lower().split()) & set(node.content.lower().split())
            if len(common_words) >= 2:
                edge = MemoryEdge(new_node.id, node_id, "related_to", weight=len(common_words)/10)
                self.edges.append(edge)
                self._save_edge(edge)
    
    def recall(self, query: str, limit: int = 10) -> List[Tuple[MemoryNode, float]]:
        """Recall memories related to a query."""
        results = []
        query_words = set(query.lower().split())
        
        for node_id, node in self.nodes.items():
            node_words = set(node.content.lower().split())
            common = query_words & node_words
            
            if common:
                base_score = len(common) / max(len(query_words), 1)
                score = base_score * node.confidence
                
                hours_old = (datetime.utcnow() - node.last_accessed).total_seconds() / 3600
                recency_boost = max(0.5, 1.0 - (hours_old / (24 * 30)))
                score *= recency_boost
                
                results.append((node, score))
                
                node.access_count += 1
                node.last_accessed = datetime.utcnow()
                self._save_node(node)
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    def recall_semantic(self, query: str, limit: int = 5) -> List[Tuple[MemoryNode, float]]:
        """Semantic recall using query expansion + keyword matching."""
        try:
            expanded = self._expand_query(query)
            expanded_words = set(expanded.lower().split())
            
            results = []
            for node_id, node in self.nodes.items():
                node_words = set(node.content.lower().split())
                common = expanded_words & node_words
                
                if common:
                    original_words = set(query.lower().split())
                    original_matches = len(common & original_words)
                    expanded_matches = len(common) - original_matches
                    
                    base_score = (original_matches * 2 + expanded_matches) / max(len(expanded_words), 1)
                    score = base_score * node.confidence
                    
                    hours_old = (datetime.utcnow() - node.last_accessed).total_seconds() / 3600
                    recency_boost = max(0.5, 1.0 - (hours_old / (24 * 30)))
                    score *= recency_boost
                    
                    results.append((node, score))
                    
                    node.access_count += 1
                    node.last_accessed = datetime.utcnow()
            
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
            
        except Exception as e:
            logger.warning(f"Semantic recall failed: {e}, falling back to keyword")
            return self.recall(query, limit)
    
    def _expand_query(self, query: str) -> str:
        """Expand query with related terms."""
        expansions = {
            "like": ["love", "enjoy", "favorite", "prefer", "good"],
            "love": ["like", "enjoy", "favorite", "prefer", "adore"],
            "enjoy": ["like", "love", "favorite", "prefer"],
            "favorite": ["like", "love", "best", "prefer"],
            "prefer": ["like", "love", "favorite"],
            "food": ["eat", "pizza", "coffee", "meal"],
            "eat": ["food", "pizza", "coffee", "meal"],
            "pizza": ["food", "eat", "favorite"],
            "coffee": ["drink", "food", "favorite"],
            "sport": ["basketball", "football", "soccer", "game"],
            "game": ["sport", "basketball", "football"],
            "hobby": ["like", "enjoy", "do", "interest"],
            "what": ["which", "who", "where", "favorite", "like"],
            "who": ["name", "called"],
            "name": ["who", "called"],
            "do": ["like", "enjoy", "hobby", "activity"],
            "my": ["i", "me"],
            "i": ["my", "me"],
            "business": ["company", "work", "job", "service"],
            "company": ["business", "work", "job"],
            "run": ["business", "work", "own"],
            "own": ["business", "run", "have"],
        }
        
        words = query.lower().split()
        expanded = list(words)
        
        for word in words:
            if word in expansions:
                expanded.extend(expansions[word])
        
        return " ".join(expanded)
    
    def get_personality_traits(self) -> List[Dict]:
        """Extract learned personality traits"""
        traits = []
        for node in self.nodes.values():
            if node.type in ["preference", "value", "personality"]:
                traits.append({
                    "content": node.content,
                    "confidence": node.confidence,
                    "evidence_count": node.activation_count
                })
        return sorted(traits, key=lambda x: x["confidence"] * x["evidence_count"], reverse=True)
    
    def get_memory_summary(self) -> Dict:
        """Get summary of cumulative memory"""
        by_type = defaultdict(int)
        for node in self.nodes.values():
            by_type[node.type] += 1
        
        return {
            "total_memories": len(self.nodes),
            "total_connections": len(self.edges),
            "memory_types": dict(by_type),
        }
    
    def export(self) -> Dict:
        """Export all memory"""
        return {
            "user_id": self.user_id,
            "exported_at": datetime.utcnow().isoformat(),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.__dict__ for e in self.edges]
        }
    
    def delete_all(self):
        """Delete all memory (GDPR compliance)"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memory_events WHERE user_id = %s", (self.user_id,))
        cursor.execute("DELETE FROM memory_edges WHERE user_id = %s", (self.user_id,))
        cursor.execute("DELETE FROM memory_nodes WHERE user_id = %s", (self.user_id,))
        conn.commit()
        conn.close()
        
        self.nodes.clear()
        self.edges.clear()
        logger.warning(f"All memory deleted for user {self.user_id}")
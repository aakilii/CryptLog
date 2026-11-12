"""
Network Analysis Agent Service
Provides network flow analysis, exfiltration detection, and traffic statistics.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from operation_room.database import open_vault
from operation_room.config import settings

logger = logging.getLogger(__name__)


def _get_table_names(conn) -> List[str]:
    """Get table names using DuckDB SHOW TABLES."""
    try:
        tables = conn.execute("SHOW TABLES").fetchall()
        return [t[0] for t in tables]
    except:
        return []


def run_network_analysis(
    case_id: str,
    source_filters: List[str] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute network analysis on case data."""
    run_id = f"net-{uuid.uuid4().hex[:8]}"
    
    conn = open_vault(case_id)
    try:
        # Check available tables
        table_names = _get_table_names(conn)
        
        # Try network_flows first, then fall back to unified_timeline
        if 'network_flows' in table_names:
            return _analyze_network_flows(conn, run_id, source_filters, time_start, time_end)
        elif 'unified_timeline' in table_names:
            return _analyze_timeline_network(conn, run_id, 'unified_timeline', source_filters, time_start, time_end)
        elif 'timeline' in table_names:
            return _analyze_timeline_network(conn, run_id, 'timeline', source_filters, time_start, time_end)
        else:
            return {
                "run_id": run_id,
                "status": "completed",
                "message": "No data found. Import network or timeline data first.",
                "total_flows": 0,
                "suspicious_flows": 0,
                "exfil_candidates": 0,
                "total_bytes_out": 0
            }
    finally:
        conn.close()


def _analyze_network_flows(conn, run_id: str, source_filters: List[str], time_start: str, time_end: str) -> Dict[str, Any]:
    """Analyze dedicated network_flows table."""
    where_clauses = ["1=1"]
    
    if time_start:
        where_clauses.append(f"timestamp >= '{time_start}'")
    if time_end:
        where_clauses.append(f"timestamp <= '{time_end}'")
    if source_filters:
        sources_str = ", ".join(f"'{s}'" for s in source_filters)
        where_clauses.append(f"source_ip IN ({sources_str})")
    
    where_sql = " AND ".join(where_clauses)
    
    total_flows = conn.execute(f"SELECT COUNT(*) FROM network_flows WHERE {where_sql}").fetchone()[0]
    
    try:
        suspicious = conn.execute(f"""
            SELECT COUNT(*) FROM network_flows 
            WHERE {where_sql}
            AND (bytes_out > 10000000 OR dest_port IN (22, 23, 3389, 4444, 5555))
        """).fetchone()[0]
    except:
        suspicious = 0
    
    try:
        bytes_out = conn.execute(f"SELECT COALESCE(SUM(bytes_out), 0) FROM network_flows WHERE {where_sql}").fetchone()[0]
    except:
        bytes_out = 0
    
    return {
        "run_id": run_id,
        "status": "completed",
        "total_flows": total_flows,
        "suspicious_flows": suspicious,
        "exfil_candidates": 0,
        "total_bytes_out": bytes_out,
        "timestamp": datetime.utcnow().isoformat()
    }


def _analyze_timeline_network(conn, run_id: str, table: str, source_filters: List[str], time_start: str, time_end: str) -> Dict[str, Any]:
    """Analyze network-like events from timeline data."""
    ts_col = 'normalised_ts' if table == 'unified_timeline' else 'timestamp'
    
    where_clauses = ["1=1"]
    
    if time_start:
        where_clauses.append(f"{ts_col} >= '{time_start}'")
    if time_end:
        where_clauses.append(f"{ts_col} <= '{time_end}'")
    if source_filters:
        sources_str = ", ".join(f"'{s}'" for s in source_filters)
        where_clauses.append(f"source_system IN ({sources_str})")
    
    where_sql = " AND ".join(where_clauses)
    
    # Count total events as "flows"
    total = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where_sql}").fetchone()[0]
    
    # Count suspicious actions
    try:
        suspicious = conn.execute(f"""
            SELECT COUNT(*) FROM {table}
            WHERE {where_sql}
            AND (action IN ('EXPORT', 'FILE_WRITE', 'DOWNLOAD', 'UPLOAD', 'SEND') 
                 OR severity IN ('HIGH', 'CRITICAL'))
        """).fetchone()[0]
    except:
        suspicious = 0
    
    # Count exfil candidates
    try:
        exfil = conn.execute(f"""
            SELECT COUNT(*) FROM {table}
            WHERE {where_sql}
            AND action IN ('EXPORT', 'FILE_WRITE', 'DOWNLOAD', 'UPLOAD')
        """).fetchone()[0]
    except:
        exfil = 0
    
    # Estimate bytes - use target length as proxy
    try:
        bytes_est = conn.execute(f"""
            SELECT COALESCE(SUM(LENGTH(COALESCE(target, ''))), 0) FROM {table}
            WHERE {where_sql}
        """).fetchone()[0]
    except:
        bytes_est = 0
    
    return {
        "run_id": run_id,
        "status": "completed",
        "total_flows": total,
        "suspicious_flows": suspicious,
        "exfil_candidates": exfil,
        "total_bytes_out": bytes_est,
        "timestamp": datetime.utcnow().isoformat()
    }


def get_network_flows(
    case_id: str,
    run_id: Optional[str] = None,
    suspicious_only: bool = False,
    direction: Optional[str] = None,
    protocol: Optional[str] = None,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """Get network flow records. Falls back to unified_timeline if network_flows doesn't exist."""
    conn = open_vault(case_id)
    try:
        # Check if network_flows table exists
        has_network_flows = False
        try:
            conn.execute("SELECT 1 FROM network_flows LIMIT 1")
            has_network_flows = True
        except:
            pass
        
        if has_network_flows:
            where_clauses = ["1=1"]
            params = []
            
            if suspicious_only:
                where_clauses.append("(bytes_sent > 10000000 OR is_suspicious = true)")
            if direction:
                where_clauses.append("direction = ?")
                params.append(direction)
            if protocol:
                where_clauses.append("protocol = ?")
                params.append(protocol)
            
            query = f"""
            SELECT 
                flow_id,
                src_ip as source_ip,
                dst_ip as dest_ip,
                src_port as source_port,
                dst_port as dest_port,
                protocol,
                bytes_sent,
                bytes_received,
                UPPER(direction) as direction,
                actor,
                source_system,
                is_suspicious,
                suspicion_reason,
                threat_score,
                anomaly_score,
                normalised_ts
            FROM network_flows 
            WHERE {" AND ".join(where_clauses)}
            ORDER BY normalised_ts DESC
            LIMIT {limit}
            """
            
            results = conn.execute(query, params).fetchall()
            columns = ['flow_id', 'source_ip', 'dest_ip', 'source_port', 'dest_port', 'protocol', 
                      'bytes_sent', 'bytes_received', 'direction', 'actor', 'source_system', 'is_suspicious',
                      'suspicion_reason', 'threat_score', 'anomaly_score', 'normalised_ts']
            
            return [dict(zip(columns, row)) for row in results]
        
        # Fallback to unified_timeline - synthesize network-like flows
        tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
        table = 'unified_timeline' if 'unified_timeline' in tables else ('timeline' if 'timeline' in tables else None)
        
        if not table:
            return []
        
        ts_col = 'normalised_ts' if table == 'unified_timeline' else 'timestamp'
        
        where_clauses = ["1=1"]
        if suspicious_only:
            where_clauses.append("(severity IN ('HIGH', 'CRITICAL') OR action IN ('EXPORT', 'UPLOAD', 'DOWNLOAD'))")
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
        SELECT 
            tl_event_id as flow_id,
            actor as source_ip,
            COALESCE(target, 'internal') as dest_ip,
            source_system as protocol,
            action,
            severity,
            {ts_col} as timestamp,
            LENGTH(COALESCE(detail, '')) * 100 as bytes_out,
            CASE WHEN action IN ('EXPORT', 'UPLOAD', 'DOWNLOAD', 'SEND') THEN 'outbound' ELSE 'internal' END as direction
        FROM {table}
        WHERE {where_sql}
        ORDER BY {ts_col} DESC
        LIMIT {limit}
        """
        
        results = conn.execute(query).fetchall()
        columns = ['flow_id', 'source_ip', 'dest_ip', 'protocol', 'action', 'severity', 'timestamp', 'bytes_out', 'direction']
        
        return [dict(zip(columns, row)) for row in results]
        
    except Exception as e:
        logger.error(f"Error getting network flows: {e}")
        return []
    finally:
        conn.close()


def get_exfil_candidates(case_id: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get potential data exfiltration events.
    
    Detection criteria:
    - Large data transfers (>100KB) or EXPORT/UPLOAD/SEND actions
    - Outbound to external IPs
    - Unusual ports or patterns
    
    Falls back to unified_timeline if network_flows isn't present or has no exfil candidates.
    """
    conn = open_vault(case_id)
    candidates = []
    
    try:
        # Try network_flows table first
        try:
            columns_result = conn.execute("DESCRIBE network_flows").fetchall()
            column_names = [col[0] for col in columns_result]
            
            # Detect actual column names (may vary by import)
            src_col = next((c for c in ['src_ip', 'source_ip', 'SrcIP', 'source'] if c in column_names), None)
            dst_col = next((c for c in ['dst_ip', 'dest_ip', 'DstIP', 'destination'] if c in column_names), None)
            port_col = next((c for c in ['dst_port', 'dest_port', 'DstPort', 'port'] if c in column_names), None)
            bytes_col = next((c for c in ['bytes_sent', 'bytes_out', 'BytesSent', 'bytes'] if c in column_names), None)
            ts_col = next((c for c in ['normalised_ts', 'timestamp', 'ts', 'time'] if c in column_names), None)
            
            if all([src_col, dst_col, bytes_col]):
                # Build dynamic query based on actual columns
                where_clause = f"({bytes_col} > 100000" if bytes_col else "(1=1"
                if port_col:
                    where_clause += f" OR {port_col} IN (443, 80, 8080, 22, 21, 3389))"
                else:
                    where_clause += ")"
                
                select_parts = [
                    f"{src_col} as src_ip",
                    f"{dst_col} as dst_ip",
                    f"{port_col} as dst_port" if port_col else "0 as dst_port",
                    f"SUM(COALESCE({bytes_col}, 0)) as total_bytes" if bytes_col else "0 as total_bytes",
                    "COUNT(*) as connection_count",
                ]
                if ts_col:
                    select_parts.extend([f"MIN({ts_col}) as first_seen", f"MAX({ts_col}) as last_seen"])
                else:
                    select_parts.extend(["NULL as first_seen", "NULL as last_seen"])
                
                query = f"""
                SELECT {', '.join(select_parts)}
                FROM network_flows
                WHERE {where_clause}
                GROUP BY {src_col}, {dst_col}{', ' + port_col if port_col else ''}
                ORDER BY total_bytes DESC
                LIMIT 50
                """
                
                results = conn.execute(query).fetchall()
                candidates = [dict(zip(
                    ['source_ip', 'dest_ip', 'dest_port', 'total_bytes', 'connection_count', 'first_seen', 'last_seen'],
                    row
                )) for row in results]
        except Exception as e:
            logger.debug(f"network_flows query failed: {e}")
        
        # If no network_flows results, try unified_timeline for exfil-like actions
        if not candidates:
            try:
                # Check for unified_timeline
                tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
                table = 'unified_timeline' if 'unified_timeline' in tables else ('timeline' if 'timeline' in tables else None)
                
                if table:
                    ts_col = 'normalised_ts' if table == 'unified_timeline' else 'timestamp'
                    
                    query = f"""
                    SELECT 
                        actor as source_ip,
                        COALESCE(target, 'unknown') as dest_ip,
                        0 as dest_port,
                        LENGTH(COALESCE(target, '')) * 1000 as total_bytes,
                        COUNT(*) as connection_count,
                        MIN({ts_col}) as first_seen,
                        MAX({ts_col}) as last_seen,
                        action
                    FROM {table}
                    WHERE action IN ('EXPORT', 'UPLOAD', 'FILE_WRITE', 'SEND', 'DOWNLOAD', 'COPY')
                       OR severity IN ('HIGH', 'CRITICAL')
                    GROUP BY actor, target, action
                    ORDER BY connection_count DESC
                    LIMIT 50
                    """
                    
                    results = conn.execute(query).fetchall()
                    candidates = [dict(zip(
                        ['source_ip', 'dest_ip', 'dest_port', 'total_bytes', 'connection_count', 'first_seen', 'last_seen', 'action'],
                        row
                    )) for row in results]
            except Exception as e:
                logger.debug(f"Timeline exfil query failed: {e}")
        
        # Calculate suspicion score for each candidate
        for candidate in candidates:
            score = 0.0
            
            # Large transfer score
            total_bytes = candidate.get('total_bytes', 0) or 0
            bytes_mb = total_bytes / (1024 * 1024)
            if bytes_mb > 100:
                score += 0.4
            elif bytes_mb > 10:
                score += 0.3
            elif bytes_mb > 1:
                score += 0.2
            else:
                score += 0.1
            
            # Suspicious action types
            action = candidate.get('action', '')
            if action in ['EXPORT', 'UPLOAD', 'SEND']:
                score += 0.3
            elif action in ['FILE_WRITE', 'DOWNLOAD', 'COPY']:
                score += 0.2
            
            # Suspicious ports
            port = candidate.get('dest_port', 0) or 0
            if port in [443, 22, 21]:  # HTTPS, SSH, FTP
                score += 0.3
            elif port in [80, 8080, 3389]:  # HTTP, RDP
                score += 0.2
            
            # Connection pattern
            conn_count = candidate.get('connection_count', 0) or 0
            if conn_count > 100:
                score += 0.2
            elif conn_count > 10:
                score += 0.1
            
            # External IP (crude check)
            dest_ip = candidate.get('dest_ip', '') or ''
            if dest_ip and not any(dest_ip.startswith(p) for p in ['192.168.', '10.', '172.16.', '127.']):
                score += 0.2
            
            candidate['suspicion_score'] = round(min(1.0, score), 3)
            candidate['risk_level'] = 'HIGH' if score >= 0.7 else ('MEDIUM' if score >= 0.5 else 'LOW')
            
            # Convert datetime objects to strings for JSON serialization
            for key in ['first_seen', 'last_seen']:
                if candidate.get(key) is not None:
                    if hasattr(candidate[key], 'isoformat'):
                        candidate[key] = candidate[key].isoformat()
                    else:
                        candidate[key] = str(candidate[key])
        
        return candidates
    except Exception as e:
        logger.error(f"Error getting exfil candidates: {e}")
        return []
    finally:
        conn.close()


def get_destinations(case_id: str, run_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get destination IP statistics."""
    conn = open_vault(case_id)
    try:
        try:
            conn.execute("SELECT 1 FROM network_flows LIMIT 1")
        except:
            return []
        
        # Use correct column names: dst_ip, bytes_sent, bytes_received
        query = """
        SELECT 
            dst_ip,
            COUNT(*) as connection_count,
            SUM(bytes_sent) as total_bytes_out,
            SUM(bytes_received) as total_bytes_in
        FROM network_flows
        GROUP BY dst_ip
        ORDER BY connection_count DESC
        LIMIT 100
        """
        
        results = conn.execute(query).fetchall()
        columns = ['dest_ip', 'connection_count', 'total_bytes_out', 'total_bytes_in']
        
        return [dict(zip(columns, row)) for row in results]
    except Exception as e:
        logger.error(f"Error getting destinations: {e}")
        return []
    finally:
        conn.close()


def get_network_runs(case_id: str) -> List[Dict[str, Any]]:
    """List past network analysis runs."""
    # For now, return empty - runs are not persisted
    return []


def get_network_flows_search(
    case_id: str,
    payload: Dict[str, Any],
    limit: int = 500,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Search network flows with filters."""
    return get_network_flows(case_id, limit=limit)


def get_network_flows_stats_search(
    case_id: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Get network flow statistics."""
    conn = open_vault(case_id)
    try:
        try:
            # Use correct column names: src_ip, dst_ip, bytes_sent, bytes_received
            stats = conn.execute("""
            SELECT 
                COUNT(*) as total_flows,
                SUM(bytes_sent) as total_bytes_out,
                SUM(bytes_received) as total_bytes_in,
                COUNT(DISTINCT src_ip) as unique_sources,
                COUNT(DISTINCT dst_ip) as unique_destinations
            FROM network_flows
            """).fetchone()
            
            return {
                "total_flows": stats[0] or 0,
                "total_bytes_out": stats[1] or 0,
                "total_bytes_in": stats[2] or 0,
                "unique_sources": stats[3] or 0,
                "unique_destinations": stats[4] or 0
            }
        except:
            return {"total_flows": 0, "total_bytes_out": 0, "total_bytes_in": 0, "unique_sources": 0, "unique_destinations": 0}
    finally:
        conn.close()


def get_network_distinct(case_id: str, field_name: str) -> List[str]:
    """Get distinct values for a field."""
    # Map user-friendly names to actual column names
    field_map = {
        'source_ip': 'src_ip',
        'dest_ip': 'dst_ip', 
        'dest_port': 'dst_port',
        'protocol': 'protocol',
        'direction': 'direction'
    }
    
    allowed_fields = list(field_map.keys())
    if field_name not in allowed_fields:
        raise ValueError(f"Field {field_name} not allowed")
    
    actual_field = field_map.get(field_name, field_name)
    
    conn = open_vault(case_id)
    try:
        try:
            results = conn.execute(f"SELECT DISTINCT {actual_field} FROM network_flows WHERE {actual_field} IS NOT NULL LIMIT 1000").fetchall()
            return [str(r[0]) for r in results]
        except:
            return []
    finally:
        conn.close()


def get_network_entities(
    case_id: str,
    risk_level: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get network entities (actors/IPs) with risk scoring.
    Falls back to unified_timeline if network_flows doesn't exist.
    """
    conn = open_vault(case_id)
    entities = []
    
    try:
        # Check if network_flows exists
        has_network_flows = False
        try:
            conn.execute("SELECT 1 FROM network_flows LIMIT 1")
            has_network_flows = True
        except:
            pass
        
        if has_network_flows:
            # Analyze from network_flows
            query = """
            SELECT 
                src_ip as ip_address,
                COUNT(*) as connections_count,
                SUM(bytes_sent) as total_bytes_out,
                COUNT(DISTINCT dst_ip) as unique_destinations
            FROM network_flows
            GROUP BY src_ip
            ORDER BY connections_count DESC
            LIMIT ?
            """
            results = conn.execute(query, [limit]).fetchall()
            
            for row in results:
                # Calculate risk score
                conns = row[1] or 0
                bytes_out = row[2] or 0
                dests = row[3] or 0
                
                risk_score = min(100, int(
                    (conns / 10) * 20 +  # Connection volume
                    (bytes_out / 1000000) * 30 +  # Data volume (MB)
                    (dests * 5)  # Destination diversity
                ))
                
                entities.append({
                    "entity_id": f"entity-{row[0]}",
                    "ip_address": row[0],
                    "connections_count": conns,
                    "total_bytes_out": bytes_out,
                    "unique_destinations": dests,
                    "risk_score": risk_score,
                    "risk_level": "HIGH" if risk_score >= 70 else ("MEDIUM" if risk_score >= 40 else "LOW"),
                    "domain": None
                })
        else:
            # Fallback to unified_timeline
            tables = [t[0] for t in conn.execute("SHOW TABLES").fetchall()]
            table = 'unified_timeline' if 'unified_timeline' in tables else ('timeline' if 'timeline' in tables else None)
            
            if table:
                ts_col = 'normalised_ts' if table == 'unified_timeline' else 'timestamp'
                
                query = f"""
                SELECT 
                    actor as ip_address,
                    COUNT(*) as connections_count,
                    COUNT(DISTINCT target) as unique_destinations,
                    COUNT(DISTINCT action) as action_types,
                    SUM(CASE WHEN severity IN ('HIGH', 'CRITICAL') THEN 1 ELSE 0 END) as high_severity_count
                FROM {table}
                WHERE actor IS NOT NULL
                GROUP BY actor
                ORDER BY connections_count DESC
                LIMIT {limit}
                """
                results = conn.execute(query).fetchall()
                
                for row in results:
                    conns = row[1] or 0
                    dests = row[2] or 0
                    actions = row[3] or 0
                    high_sev = row[4] or 0
                    
                    # Calculate risk based on activity pattern
                    risk_score = min(100, int(
                        (conns / 20) * 20 +  # Activity volume
                        (dests * 3) +  # Target diversity
                        (actions * 5) +  # Action diversity
                        (high_sev * 15)  # High severity events
                    ))
                    
                    entities.append({
                        "entity_id": f"entity-{hash(row[0]) % 10000}",
                        "ip_address": row[0],
                        "connections_count": conns,
                        "unique_destinations": dests,
                        "action_types": actions,
                        "high_severity_count": high_sev,
                        "risk_score": risk_score,
                        "risk_level": "HIGH" if risk_score >= 70 else ("MEDIUM" if risk_score >= 40 else "LOW"),
                        "domain": None
                    })
        
        # Filter by risk level if specified
        if risk_level:
            risk_level_upper = risk_level.upper()
            entities = [e for e in entities if e.get("risk_level") == risk_level_upper]
        
        return entities
        
    except Exception as e:
        logger.error(f"Error getting network entities: {e}")
        return []
    finally:
        conn.close()

async def chat_with_agent(case_id: str, query: str, llm_provider: str = "ollama", run_id: str | None = None) -> dict:
    from operation_room.services.llm_provider import get_llm
    llm = get_llm(llm_provider)
    system = "You are the Network Agent. Respond to queries focusing strictly on exfiltration, IPs, and ports."
    response = await llm.generate("Investigator Question:\n" + query, system=system)
    return {"response": response, "log_id": "network-log", "llm_provider": llm_provider, "agent_routed": "network_agent"}


async def chat_with_agent(case_id: str, query: str, llm_provider: str = "ollama", run_id: str | None = None) -> dict:
    from operation_room.services.llm_provider import get_llm
    llm = get_llm(llm_provider)
    system = "You are the Network Agent. Respond to queries focusing strictly on exfiltration, IPs, and ports."
    response = await llm.generate("Investigator Question:\n" + query, system=system)
    return {"response": response, "log_id": "network-log", "llm_provider": llm_provider, "agent_routed": "network_agent"}


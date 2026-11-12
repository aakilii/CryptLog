#!/usr/bin/env python3
"""
NFLIP Multi-Agent CLI — Command-line interface for the report automation system.

Usage:
    python -m app.cli generate --case CASE-001 --scenario "Suspected malware..."
    python -m app.cli analyze --scenario "Network intrusion detected..."
    python -m app.cli research --query "memory forensics"
    python -m app.cli status --run-id <run_id>
    python -m app.cli health

Author: NFLIP Development Team
Version: 1.0.0
"""

import argparse
import asyncio
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from operation_room.config import settings
from operation_room.services.llm_service import get_llm_service
from operation_room.services.agent_runner import get_runner_service, RunStatus
from operation_room.agents.research.knowledge_base import knowledge_base, ResearchCategory
from operation_room.agents.hypothesis.hypothesis_agent import HypothesisAnalysisAgent
from operation_room.agents.integration_layer import PipelineExecutor


# ═══════════════════════════════════════════════════════════════════════════════
# COLORS FOR TERMINAL OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    
    @classmethod
    def disable(cls):
        """Disable colors (for non-TTY output)."""
        cls.HEADER = ''
        cls.BLUE = ''
        cls.CYAN = ''
        cls.GREEN = ''
        cls.WARNING = ''
        cls.FAIL = ''
        cls.ENDC = ''
        cls.BOLD = ''
        cls.UNDERLINE = ''


def print_header(text: str):
    """Print a header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.ENDC}")


def print_json(data: dict, indent: int = 2):
    """Print formatted JSON."""
    print(json.dumps(data, indent=indent, default=str))


# ═══════════════════════════════════════════════════════════════════════════════
# COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_generate(args):
    """Generate an automated report."""
    print_header("Multi-Agent Report Generation")
    
    print_info(f"Case ID: {args.case_id}")
    print_info(f"Report Type: {args.report_type}")
    print_info(f"LLM Provider: {args.provider}")
    
    if args.scenario:
        scenario = args.scenario
    elif args.scenario_file:
        with open(args.scenario_file, 'r') as f:
            scenario = f.read()
    else:
        print_error("No scenario provided. Use --scenario or --scenario-file")
        return 1
        
    print_info(f"Scenario: {scenario[:100]}..." if len(scenario) > 100 else f"Scenario: {scenario}")
    print()
    
    # Progress callback
    def on_progress(progress):
        pct = int(progress.percentage)
        bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
        print(f"\r{Colors.CYAN}[{bar}] {pct}% - {progress.message}{Colors.ENDC}", end='', flush=True)
        
    # Create and execute run
    runner = get_runner_service()
    run = runner.create_run(
        case_id=args.case_id,
        scenario=scenario,
        report_type=args.report_type,
        llm_provider=args.provider
    )
    
    print_info(f"Run ID: {run.run_id}")
    print()
    
    # Execute
    run = await runner.execute_run(run, timeout=args.timeout, on_progress=on_progress)
    print()  # New line after progress bar
    
    if run.status == RunStatus.COMPLETED:
        print_success("Report generation completed!")
        
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(run.result, f, indent=2, default=str)
            print_success(f"Report saved to: {output_path}")
        else:
            print()
            print_header("Results")
            
            result = run.result or {}
            print(f"Hypotheses: {len(result.get('hypotheses', []))}")
            print(f"Entities: {len(result.get('entities', []))}")
            print(f"Evidence Items: {result.get('evidence_count', 0)}")
            
            confidence = result.get('confidence', {})
            if confidence:
                print(f"\nOverall Confidence: {confidence.get('overall_case_confidence', 0):.2%}")
                print(f"Confidence Level: {confidence.get('overall_confidence_level', 'N/A')}")
                
            if args.verbose:
                print()
                print_header("Full Result")
                print_json(result)
                
        return 0
    else:
        print_error(f"Report generation failed: {run.error}")
        return 1


async def cmd_analyze(args):
    """Analyze a scenario and generate hypotheses."""
    print_header("Hypothesis Analysis")
    
    if args.scenario:
        scenario = args.scenario
    elif args.scenario_file:
        with open(args.scenario_file, 'r') as f:
            scenario = f.read()
    else:
        print_error("No scenario provided. Use --scenario or --scenario-file")
        return 1
        
    print_info(f"Scenario: {scenario[:200]}..." if len(scenario) > 200 else f"Scenario: {scenario}")
    print_info(f"LLM Provider: {args.provider}")
    print()
    
    # Use LLM service for analysis
    llm_service = get_llm_service(args.provider)
    
    print_info("Analyzing scenario...")
    response = await llm_service.analyze_hypothesis(scenario)
    
    if response.success and response.parsed_json:
        print_success("Analysis complete!")
        print()
        
        result = response.parsed_json
        
        # Print hypotheses
        hypotheses = result.get('hypotheses', [])
        print_header(f"Generated Hypotheses ({len(hypotheses)})")
        for i, h in enumerate(hypotheses, 1):
            print(f"\n{Colors.BOLD}H{i}: {h.get('statement', 'N/A')}{Colors.ENDC}")
            print(f"   Probability: {h.get('initial_probability', 0):.0%}")
            print(f"   Attack Vectors: {', '.join(h.get('attack_vectors', []))}")
            print(f"   Evidence Needed: {', '.join(h.get('evidence_required', [])[:3])}")
            
        # Print entities
        entities = result.get('entities', [])
        if entities:
            print()
            print_header(f"Extracted Entities ({len(entities)})")
            for e in entities[:10]:
                print(f"   • {e.get('name', 'N/A')} ({e.get('type', 'unknown')})")
                
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(result, f, indent=2)
            print_success(f"Results saved to: {args.output}")
            
        return 0
    else:
        print_error(f"Analysis failed: {response.error}")
        return 1


async def cmd_research(args):
    """Search the research knowledge base."""
    print_header("Research Knowledge Base")
    
    if args.stats:
        stats = knowledge_base.get_statistics()
        print(f"Total Methodologies: {stats['total_methodologies']}")
        print()
        print("By Category:")
        for cat, count in sorted(stats['categories'].items(), key=lambda x: -x[1]):
            print(f"   {cat}: {count}")
        return 0
        
    if args.category:
        try:
            cat = ResearchCategory(args.category)
            methodologies = knowledge_base.get_by_category(cat)
        except ValueError:
            print_error(f"Unknown category: {args.category}")
            print_info("Available categories: " + ", ".join([c.value for c in ResearchCategory]))
            return 1
    elif args.module:
        methodologies = knowledge_base.get_by_module(args.module)
    elif args.query:
        methodologies = knowledge_base.search(args.query)
    else:
        methodologies = knowledge_base.list_all()[:args.limit]
        
    print(f"Found {len(methodologies)} methodologies\n")
    
    for m in methodologies[:args.limit]:
        if hasattr(m, 'to_dict'):
            m = m.to_dict()
        print(f"{Colors.BOLD}{m.get('name', 'N/A')}{Colors.ENDC}")
        print(f"   Category: {m.get('category', 'N/A')}")
        print(f"   Authors: {', '.join(m.get('authors', []))}")
        print(f"   Use Cases: {', '.join(m.get('use_cases', [])[:2])}")
        print()
        
    return 0


async def cmd_status(args):
    """Check status of a run."""
    runner = get_runner_service()
    
    if args.run_id:
        run = runner.get_run(args.run_id)
        if not run:
            print_error(f"Run not found: {args.run_id}")
            return 1
            
        print_header(f"Run Status: {args.run_id}")
        print_json(run.to_dict())
        
        if args.logs:
            print()
            print_header("Logs")
            for log in run.logs:
                print(log)
                
    else:
        runs = runner.list_runs(limit=args.limit)
        print_header(f"Recent Runs ({len(runs)})")
        
        for run in runs:
            status_color = {
                RunStatus.COMPLETED: Colors.GREEN,
                RunStatus.FAILED: Colors.FAIL,
                RunStatus.RUNNING: Colors.CYAN,
                RunStatus.PENDING: Colors.WARNING,
            }.get(run.status, '')
            
            print(f"{status_color}[{run.status.value:10}]{Colors.ENDC} "
                  f"{run.run_id[:8]}... | {run.case_id} | "
                  f"{run.started_at.strftime('%Y-%m-%d %H:%M') if run.started_at else 'N/A'}")
                  
    return 0


async def cmd_health(args):
    """Check system health."""
    print_header("System Health")
    
    runner = get_runner_service()
    health = runner.get_health()
    
    print(f"Status: {Colors.GREEN if health['status'] == 'healthy' else Colors.FAIL}{health['status']}{Colors.ENDC}")
    print(f"Active Runs: {health['active_runs']}/{health['max_concurrent_runs']}")
    print(f"Total Runs: {health['total_runs']}")
    print(f"Completed: {health['completed_runs']}")
    print(f"Failed: {health['failed_runs']}")
    print(f"LLM Provider: {health['llm_provider']}")
    
    print()
    print_header("LLM Metrics")
    llm = health.get('llm_metrics', {})
    print(f"Total Calls: {llm.get('total_calls', 0)}")
    print(f"Success Rate: {llm.get('success_rate', 0):.1%}")
    print(f"Avg Latency: {llm.get('avg_latency_ms', 0):.0f}ms")
    
    print()
    print_header("Research Knowledge Base")
    stats = knowledge_base.get_statistics()
    print(f"Total Methodologies: {stats['total_methodologies']}")
    print(f"Categories: {len(stats['categories'])}")
    
    return 0


async def cmd_test_llm(args):
    """Test LLM connectivity."""
    print_header("LLM Connection Test")
    
    print_info(f"Testing provider: {args.provider}")
    
    llm_service = get_llm_service(args.provider)
    
    prompt = "Respond with exactly: 'LLM connection successful'"
    print_info(f"Sending test prompt...")
    
    response = await llm_service.generate(prompt, temperature=0.1)
    
    if response.success:
        print_success(f"Connection successful!")
        print(f"Response: {response.content[:200]}")
        print(f"Latency: {response.latency_ms:.0f}ms")
        print(f"Model: {response.model}")
        return 0
    else:
        print_error(f"Connection failed: {response.error}")
        return 1


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    # Disable colors if not a TTY
    if not sys.stdout.isatty():
        Colors.disable()
        
    parser = argparse.ArgumentParser(
        description="NFLIP Multi-Agent CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate a report:
    python -m app.cli generate --case CASE-001 --scenario "Malware detected..."
    
  Analyze hypothesis:
    python -m app.cli analyze --scenario "Network intrusion on 10.0.0.1..."
    
  Search research:
    python -m app.cli research --query "volatility memory"
    
  Check health:
    python -m app.cli health
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate automated report')
    gen_parser.add_argument('--case-id', '-c', required=True, help='Case identifier')
    gen_parser.add_argument('--scenario', '-s', help='Scenario text')
    gen_parser.add_argument('--scenario-file', '-f', help='File containing scenario')
    gen_parser.add_argument('--report-type', '-t', default='technical',
                           choices=['technical', 'executive', 'regulatory'])
    gen_parser.add_argument('--provider', '-p', default=settings.LLM_PROVIDER,
                           choices=['ollama', 'gemini'])
    gen_parser.add_argument('--output', '-o', help='Output file for results')
    gen_parser.add_argument('--timeout', type=int, default=300, help='Timeout in seconds')
    gen_parser.add_argument('--verbose', '-v', action='store_true')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze scenario for hypotheses')
    analyze_parser.add_argument('--scenario', '-s', help='Scenario text')
    analyze_parser.add_argument('--scenario-file', '-f', help='File containing scenario')
    analyze_parser.add_argument('--provider', '-p', default=settings.LLM_PROVIDER)
    analyze_parser.add_argument('--output', '-o', help='Output file')
    
    # Research command
    research_parser = subparsers.add_parser('research', help='Search research knowledge base')
    research_parser.add_argument('--query', '-q', help='Search query')
    research_parser.add_argument('--category', '-c', help='Filter by category')
    research_parser.add_argument('--module', '-m', help='Filter by module')
    research_parser.add_argument('--stats', action='store_true', help='Show statistics')
    research_parser.add_argument('--limit', '-l', type=int, default=10)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Check run status')
    status_parser.add_argument('--run-id', '-r', help='Specific run ID')
    status_parser.add_argument('--logs', action='store_true', help='Show logs')
    status_parser.add_argument('--limit', '-l', type=int, default=10)
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check system health')
    
    # Test LLM command
    test_parser = subparsers.add_parser('test-llm', help='Test LLM connection')
    test_parser.add_argument('--provider', '-p', default=settings.LLM_PROVIDER)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
        
    # Map commands to handlers
    commands = {
        'generate': cmd_generate,
        'analyze': cmd_analyze,
        'research': cmd_research,
        'status': cmd_status,
        'health': cmd_health,
        'test-llm': cmd_test_llm,
    }
    
    handler = commands.get(args.command)
    if handler:
        return asyncio.run(handler(args))
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())

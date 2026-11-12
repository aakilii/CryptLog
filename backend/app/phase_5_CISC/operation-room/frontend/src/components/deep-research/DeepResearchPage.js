/**
 * DeepResearchPage - Main Investigation Assistant Interface
 * 
 * Integrates all deep research components:
 * - Scenario input and configuration
 * - Chain-of-thought streaming
 * - Investigation plan management
 * - Human-in-loop questions
 * - Report building progress
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Stepper,
  Step,
  StepLabel,
  StepContent,
  CircularProgress,
  Alert,
  Chip,
  Grid,
  Divider,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress,
  Card,
  CardContent,
  CardActions,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Collapse,
  Tab,
  Tabs,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  HourglassEmpty as PendingIcon,
  Psychology as ThinkingIcon,
  Description as ReportIcon,
  Timeline as TimelineIcon,
  QuestionAnswer as QuestionIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon,
  Settings as SettingsIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';

import { ThoughtStream, ThoughtTree } from './index';
import { PlanEditor } from './PlanEditor';
import { HumanQuestionModal } from './HumanQuestionModal';


// Investigation phases
const PHASES = [
  { key: 'intake', label: 'Scenario Intake', description: 'Analyze investigation scenario' },
  { key: 'clarification', label: 'Clarification', description: 'Gather additional information' },
  { key: 'planning', label: 'Planning', description: 'Generate investigation plan' },
  { key: 'approval', label: 'Approval', description: 'Review and approve plan' },
  { key: 'execution', label: 'Execution', description: 'Execute investigation steps' },
  { key: 'synthesis', label: 'Synthesis', description: 'Combine findings' },
  { key: 'reporting', label: 'Reporting', description: 'Generate report' },
  { key: 'complete', label: 'Complete', description: 'Investigation complete' },
];


const PHASE_INDEX = {
  intake: 0,
  clarification: 1,
  planning: 2,
  approval: 3,
  execution: 4,
  synthesis: 5,
  reporting: 6,
  complete: 7,
};


/**
 * Main Deep Research Investigation Page
 */
export function DeepResearchPage({ caseId }) {
  // Investigation state
  const [investigationId, setInvestigationId] = useState(null);
  const [phase, setPhase] = useState('intake');
  const [status, setStatus] = useState('idle'); // idle, running, paused, complete, error
  const [error, setError] = useState(null);
  
  // Input state
  const [scenario, setScenario] = useState('');
  const [objectives, setObjectives] = useState([]);
  const [newObjective, setNewObjective] = useState('');
  const [mode, setMode] = useState('focused');
  const [timeRangeStart, setTimeRangeStart] = useState('');
  const [timeRangeEnd, setTimeRangeEnd] = useState('');
  
  // Components state
  const [thoughts, setThoughts] = useState([]);
  const [plan, setPlan] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [reportProgress, setReportProgress] = useState(null);
  
  // UI state
  const [activeTab, setActiveTab] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [llmProvider, setLlmProvider] = useState('ollama');
  
  // Refs
  const eventSourceRef = useRef(null);
  
  // API base
  const API_BASE = '/api/deep-research';
  
  /**
   * Start a new investigation
   */
  const startInvestigation = useCallback(async () => {
    try {
      setStatus('running');
      setError(null);
      
      const response = await fetch(`${API_BASE}/orchestrator/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          scenario,
          objectives,
          mode,
          time_range_start: timeRangeStart || null,
          time_range_end: timeRangeEnd || null,
        }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to start: ${response.statusText}`);
      }
      
      const data = await response.json();
      setInvestigationId(data.investigation_id);
      setPhase(data.phase);
      
      // Start event stream
      connectEventStream(data.investigation_id);
      
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  }, [caseId, scenario, objectives, mode, timeRangeStart, timeRangeEnd]);
  
  /**
   * Connect to SSE event stream
   */
  const connectEventStream = useCallback((invId) => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    
    const es = new EventSource(`${API_BASE}/orchestrator/${invId}/stream`);
    eventSourceRef.current = es;
    
    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleEvent(data);
      } catch (err) {
        console.error('Failed to parse event:', err);
      }
    };
    
    es.onerror = () => {
      console.error('SSE connection error');
      es.close();
    };
  }, []);
  
  /**
   * Handle SSE events
   */
  const handleEvent = useCallback((event) => {
    switch (event.event) {
      case 'connected':
        if (event.context) {
          setPhase(event.context.phase);
        }
        break;
        
      case 'status_update':
        if (event.status) {
          setPhase(event.status.phase);
          if (event.status.plan_progress !== undefined) {
            setPlan(prev => prev ? { ...prev, progress: event.status.plan_progress } : null);
          }
        }
        break;
        
      case 'thought_start':
        setThoughts(prev => [...prev, {
          id: event.thought_id,
          title: event.title,
          type: event.type,
          status: 'in_progress',
          content: '',
        }]);
        break;
        
      case 'thought_content':
        setThoughts(prev => prev.map(t => 
          t.id === event.thought_id 
            ? { ...t, content: t.content + event.content }
            : t
        ));
        break;
        
      case 'thought_complete':
        setThoughts(prev => prev.map(t => 
          t.id === event.thought_id 
            ? { ...t, status: 'complete' }
            : t
        ));
        break;
        
      case 'question':
        setCurrentQuestion(event.question);
        setQuestions(prev => [...prev, event.question]);
        break;
        
      case 'phase_complete':
        setPhase(event.result?.next_phase || phase);
        break;
        
      case 'investigation_complete':
        setStatus('complete');
        setPhase('complete');
        break;
        
      case 'error':
        setError(event.message);
        setStatus('error');
        break;
        
      default:
        console.log('Unknown event:', event);
    }
  }, [phase]);
  
  /**
   * Run a specific phase
   */
  const runPhase = useCallback(async (phaseName) => {
    if (!investigationId) return;
    
    try {
      setStatus('running');
      setError(null);
      
      const response = await fetch(
        `${API_BASE}/orchestrator/${investigationId}/run/${phaseName}`,
        { method: 'POST' }
      );
      
      if (!response.ok) {
        throw new Error(`Failed to run ${phaseName}: ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Update state based on phase
      if (phaseName === 'planning' && data.plan) {
        setPlan(data.plan);
      }
      if (phaseName === 'clarification' && data.questions) {
        setQuestions(data.questions);
        if (data.questions.length > 0) {
          setCurrentQuestion(data.questions[0]);
        }
      }
      
      setPhase(data.next_phase || data.phase);
      setStatus('idle');
      
    } catch (err) {
      setError(err.message);
      setStatus('error');
    }
  }, [investigationId]);
  
  /**
   * Answer a question
   */
  const answerQuestion = useCallback(async (questionId, answer) => {
    if (!investigationId) return;
    
    try {
      await fetch(
        `${API_BASE}/investigations/${investigationId}/questions/${questionId}/answer`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question_id: questionId, answer }),
        }
      );
      
      setCurrentQuestion(null);
      
    } catch (err) {
      setError(err.message);
    }
  }, [investigationId]);
  
  /**
   * Approve the plan
   */
  const approvePlan = useCallback(async () => {
    if (!investigationId) return;
    
    try {
      await fetch(
        `${API_BASE}/investigations/${investigationId}/plan/approve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ approver: 'investigator' }),
        }
      );
      
      setPlan(prev => prev ? { ...prev, status: 'approved' } : null);
      setPhase('execution');
      
    } catch (err) {
      setError(err.message);
    }
  }, [investigationId]);
  
  /**
   * Add objective
   */
  const addObjective = useCallback(() => {
    if (newObjective.trim()) {
      setObjectives(prev => [...prev, newObjective.trim()]);
      setNewObjective('');
    }
  }, [newObjective]);
  
  /**
   * Remove objective
   */
  const removeObjective = useCallback((index) => {
    setObjectives(prev => prev.filter((_, i) => i !== index));
  }, []);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);
  
  /**
   * Render scenario input form
   */
  const renderScenarioInput = () => (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        Investigation Scenario
      </Typography>
      
      <TextField
        fullWidth
        multiline
        rows={6}
        label="Describe the scenario to investigate"
        placeholder="Example: A computer (Windows) and a mobile phone (Android) have been seized from the scene of crime..."
        value={scenario}
        onChange={(e) => setScenario(e.target.value)}
        sx={{ mb: 2 }}
      />
      
      <Typography variant="subtitle2" gutterBottom>
        Objectives
      </Typography>
      
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <TextField
          size="small"
          label="Add objective"
          value={newObjective}
          onChange={(e) => setNewObjective(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && addObjective()}
          sx={{ flex: 1 }}
        />
        <Button variant="outlined" onClick={addObjective}>
          Add
        </Button>
      </Box>
      
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 3 }}>
        {objectives.map((obj, i) => (
          <Chip
            key={i}
            label={obj}
            onDelete={() => removeObjective(i)}
          />
        ))}
      </Box>
      
      <Grid container spacing={2}>
        <Grid item xs={12} sm={4}>
          <FormControl fullWidth size="small">
            <InputLabel>Investigation Mode</InputLabel>
            <Select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              label="Investigation Mode"
            >
              <MenuItem value="focused">Focused (Faster)</MenuItem>
              <MenuItem value="brute_force">Comprehensive</MenuItem>
              <MenuItem value="hybrid">Hybrid</MenuItem>
            </Select>
          </FormControl>
        </Grid>
        <Grid item xs={12} sm={4}>
          <TextField
            fullWidth
            size="small"
            type="datetime-local"
            label="Time Range Start"
            value={timeRangeStart}
            onChange={(e) => setTimeRangeStart(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <TextField
            fullWidth
            size="small"
            type="datetime-local"
            label="Time Range End"
            value={timeRangeEnd}
            onChange={(e) => setTimeRangeEnd(e.target.value)}
            InputLabelProps={{ shrink: true }}
          />
        </Grid>
      </Grid>
      
      <Box sx={{ mt: 3, display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
        <Button
          variant="outlined"
          startIcon={<SettingsIcon />}
          onClick={() => setSettingsOpen(true)}
        >
          Settings
        </Button>
        <Button
          variant="contained"
          startIcon={<PlayIcon />}
          onClick={startInvestigation}
          disabled={!scenario.trim() || status === 'running'}
        >
          Start Investigation
        </Button>
      </Box>
    </Paper>
  );
  
  /**
   * Render phase stepper
   */
  const renderPhaseStepper = () => (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Stepper activeStep={PHASE_INDEX[phase] || 0} alternativeLabel>
        {PHASES.map((p) => (
          <Step key={p.key} completed={PHASE_INDEX[p.key] < PHASE_INDEX[phase]}>
            <StepLabel>{p.label}</StepLabel>
          </Step>
        ))}
      </Stepper>
      
      {status === 'running' && (
        <LinearProgress sx={{ mt: 2 }} />
      )}
    </Paper>
  );
  
  /**
   * Render main content based on active tab
   */
  const renderMainContent = () => {
    switch (activeTab) {
      case 0: // Thoughts
        return (
          <Box sx={{ height: 500 }}>
            <ThoughtTree
              thoughts={thoughts}
              onAnswerQuestion={answerQuestion}
            />
          </Box>
        );
        
      case 1: // Plan
        return (
          <Box>
            {plan ? (
              <PlanEditor
                plan={plan}
                onApprove={approvePlan}
                onModify={(modification) => {
                  // Handle plan modification
                  console.log('Plan modification:', modification);
                }}
                readOnly={plan.status === 'approved'}
              />
            ) : (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                Plan will be generated after scenario analysis
              </Typography>
            )}
          </Box>
        );
        
      case 2: // Report
        return (
          <Box>
            {reportProgress ? (
              <Card>
                <CardContent>
                  <Typography variant="h6">Report Progress</Typography>
                  <LinearProgress
                    variant="determinate"
                    value={reportProgress.progress * 100}
                    sx={{ my: 2 }}
                  />
                  <Typography variant="body2">
                    {reportProgress.completed} / {reportProgress.total} sections complete
                  </Typography>
                  <Typography variant="body2">
                    Estimated pages: {reportProgress.total_pages}
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button
                    startIcon={<DownloadIcon />}
                    disabled={reportProgress.progress < 1}
                  >
                    Export PDF
                  </Button>
                </CardActions>
              </Card>
            ) : (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                Report will be generated after investigation
              </Typography>
            )}
          </Box>
        );
        
      default:
        return null;
    }
  };
  
  /**
   * Render settings dialog
   */
  const renderSettingsDialog = () => (
    <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)}>
      <DialogTitle>Investigation Settings</DialogTitle>
      <DialogContent>
        <FormControl fullWidth sx={{ mt: 2 }}>
          <InputLabel>LLM Provider</InputLabel>
          <Select
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value)}
            label="LLM Provider"
          >
            <MenuItem value="ollama">Ollama (Local - Qwen3)</MenuItem>
            <MenuItem value="gemini">Gemini (Cloud)</MenuItem>
          </Select>
        </FormControl>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setSettingsOpen(false)}>Close</Button>
      </DialogActions>
    </Dialog>
  );
  
  return (
    <Box sx={{ maxWidth: 1400, mx: 'auto', p: 3 }}>
      <Typography variant="h4" gutterBottom>
        Deep Research Investigation Assistant
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        AI-powered forensic investigation with chain-of-thought reasoning
      </Typography>
      
      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      
      {!investigationId ? (
        renderScenarioInput()
      ) : (
        <>
          {renderPhaseStepper()}
          
          <Paper sx={{ p: 2, mb: 3 }}>
            <Tabs
              value={activeTab}
              onChange={(e, v) => setActiveTab(v)}
              sx={{ mb: 2 }}
            >
              <Tab
                icon={<ThinkingIcon />}
                label="Thoughts"
                iconPosition="start"
              />
              <Tab
                icon={<TimelineIcon />}
                label="Plan"
                iconPosition="start"
              />
              <Tab
                icon={<ReportIcon />}
                label="Report"
                iconPosition="start"
              />
            </Tabs>
            
            {renderMainContent()}
          </Paper>
          
          {/* Action buttons based on phase */}
          <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
            {phase === 'intake' && (
              <Button
                variant="contained"
                onClick={() => runPhase('intake')}
                disabled={status === 'running'}
              >
                Analyze Scenario
              </Button>
            )}
            {phase === 'clarification' && (
              <Button
                variant="contained"
                onClick={() => runPhase('clarification')}
                disabled={status === 'running'}
              >
                Generate Questions
              </Button>
            )}
            {phase === 'planning' && (
              <Button
                variant="contained"
                onClick={() => runPhase('planning')}
                disabled={status === 'running'}
              >
                Generate Plan
              </Button>
            )}
            {phase === 'approval' && plan && (
              <Button
                variant="contained"
                color="success"
                onClick={approvePlan}
              >
                Approve Plan
              </Button>
            )}
            {phase === 'execution' && (
              <Button
                variant="contained"
                onClick={() => runPhase('execution')}
                disabled={status === 'running'}
              >
                Execute Investigation
              </Button>
            )}
            {phase === 'reporting' && (
              <Button
                variant="contained"
                onClick={() => runPhase('reporting')}
                disabled={status === 'running'}
              >
                Generate Report
              </Button>
            )}
          </Box>
        </>
      )}
      
      {/* Human-in-loop question modal */}
      {currentQuestion && (
        <HumanQuestionModal
          question={currentQuestion}
          onAnswer={(answer) => answerQuestion(currentQuestion.id, answer)}
          onSkip={() => setCurrentQuestion(null)}
        />
      )}
      
      {renderSettingsDialog()}
    </Box>
  );
}


export default DeepResearchPage;

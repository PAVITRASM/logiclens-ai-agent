import { useState, useEffect, useRef } from 'react';
import '@/App.css';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import { Mic, MicOff, Send, Trash2, CheckCircle2, Calendar, Phone, Brain, ListTodo } from 'lucide-react';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const agentConfig = {
  task_manager: {
    title: 'Task Manager',
    icon: ListTodo,
    color: 'from-emerald-400 to-teal-500',
    bgColor: 'bg-gradient-to-br from-emerald-50 to-teal-50',
    description: 'Create, track & complete tasks',
    examples: [
      'Create task to call John',
      'Show my tasks',
      'Complete task {id}'
    ]
  },
  scheduler: {
    title: 'Smart Scheduler',
    icon: Calendar,
    color: 'from-blue-400 to-cyan-500',
    bgColor: 'bg-gradient-to-br from-blue-50 to-cyan-50',
    description: 'Schedule meetings & appointments',
    examples: [
      'Schedule meeting at 3 PM',
      'Book call at 10 AM',
      'Show my calendar'
    ]
  },
  reception: {
    title: 'Reception Agent',
    icon: Phone,
    color: 'from-amber-400 to-orange-500',
    bgColor: 'bg-gradient-to-br from-amber-50 to-orange-50',
    description: '24/7 professional call handling',
    examples: [
      'Hello, I need help',
      'Connect me to sales',
      'I have a support issue'
    ]
  },
  knowledge_base: {
    title: 'Knowledge Base',
    icon: Brain,
    color: 'from-violet-400 to-purple-500',
    bgColor: 'bg-gradient-to-br from-violet-50 to-purple-50',
    description: 'Instant answers to any question',
    examples: [
      'What are your features?',
      'Show pricing plans',
      'Company information'
    ]
  }
};

function App() {
  const [activeAgent, setActiveAgent] = useState('task_manager');
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [stats, setStats] = useState({
    tasks_created: 0,
    tasks_completed: 0,
    events_created: 0,
    calls_handled: 0,
    queries_answered: 0
  });
  const [tasks, setTasks] = useState([]);
  const [events, setEvents] = useState([]);
  const recognitionRef = useRef(null);
  const synthesisRef = useRef(window.speechSynthesis);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadStats();
    loadTasks();
    loadEvents();
    loadMessages();
    initSpeechRecognition();
  }, []);

  useEffect(() => {
    loadMessages();
  }, [activeAgent]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const initSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputText(transcript);
        handleSendMessage(transcript);
        setIsListening(false);
      };

      recognitionRef.current.onerror = () => {
        setIsListening(false);
        toast.error('Voice recognition error. Please try again.');
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };
    }
  };

  const toggleVoice = () => {
    if (!recognitionRef.current) {
      toast.error('Voice recognition not supported in your browser');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        toast.info('Listening... Speak now!');
      } catch (error) {
        toast.error('Failed to start voice recognition');
      }
    }
  };

  const speak = (text) => {
    synthesisRef.current.cancel();
    const utterance = new SpeechSynthesisUtterance(text.replace(/[*#_]/g, ''));
    utterance.rate = 0.95;
    utterance.pitch = 1.05;
    utterance.volume = 1.0;
    
    const voices = synthesisRef.current.getVoices();
    const preferredVoice = voices.find(v => 
      v.name.toLowerCase().includes('google') || 
      v.name.toLowerCase().includes('samantha') ||
      v.lang.startsWith('en')
    ) || voices[0];
    
    if (preferredVoice) utterance.voice = preferredVoice;
    synthesisRef.current.speak(utterance);
  };

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API}/stats`);
      setStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const loadTasks = async () => {
    try {
      const response = await axios.get(`${API}/tasks`);
      setTasks(response.data);
    } catch (error) {
      console.error('Error loading tasks:', error);
    }
  };

  const loadEvents = async () => {
    try {
      const response = await axios.get(`${API}/events`);
      setEvents(response.data);
    } catch (error) {
      console.error('Error loading events:', error);
    }
  };

  const loadMessages = async () => {
    try {
      const response = await axios.get(`${API}/messages?agent=${activeAgent}&limit=50`);
      setMessages(response.data);
    } catch (error) {
      console.error('Error loading messages:', error);
    }
  };

  const handleSendMessage = async (text = inputText) => {
    if (!text.trim()) return;

    try {
      const response = await axios.post(`${API}/messages`, {
        content: text,
        agent: activeAgent
      });

      setMessages(prev => [
        ...prev,
        response.data.user_message,
        response.data.assistant_message
      ]);

      speak(response.data.assistant_message.content);
      setInputText('');
      loadStats();
      loadTasks();
      loadEvents();
    } catch (error) {
      console.error('Error sending message:', error);
      toast.error('Failed to send message');
    }
  };

  const handleClearMessages = async () => {
    try {
      await axios.delete(`${API}/messages`);
      setMessages([]);
      toast.success('Conversation cleared');
    } catch (error) {
      console.error('Error clearing messages:', error);
      toast.error('Failed to clear messages');
    }
  };

  const handleAgentSwitch = (agent) => {
    setActiveAgent(agent);
    synthesisRef.current.cancel();
  };

  const currentAgent = agentConfig[activeAgent];
  const AgentIcon = currentAgent.icon;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-cyan-50">
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-6xl font-bold mb-4 bg-gradient-to-r from-blue-600 via-cyan-600 to-teal-600 bg-clip-text text-transparent">
            🔍 LogicLens AI
          </h1>
          <p className="text-2xl text-slate-600 mb-6">Multi-Agent Intelligence Platform</p>
          <div className="flex justify-center gap-4 flex-wrap">
            <Badge variant="secondary" className="text-base px-4 py-2 bg-gradient-to-r from-emerald-100 to-teal-100 text-emerald-700">
              🎙️ Voice AI
            </Badge>
            <Badge variant="secondary" className="text-base px-4 py-2 bg-gradient-to-r from-blue-100 to-cyan-100 text-blue-700">
              🤖 4 Agents
            </Badge>
            <Badge variant="secondary" className="text-base px-4 py-2 bg-gradient-to-r from-amber-100 to-orange-100 text-amber-700">
              ⚡ Real-time
            </Badge>
            <Badge variant="secondary" className="text-base px-4 py-2 bg-gradient-to-r from-violet-100 to-purple-100 text-violet-700">
              💎 Enterprise
            </Badge>
          </div>
        </div>

        {/* Stats Dashboard */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          <Card className="bg-gradient-to-br from-emerald-50 to-teal-50 border-emerald-200">
            <CardContent className="pt-6 text-center">
              <CheckCircle2 className="w-12 h-12 mx-auto mb-3 text-emerald-600" />
              <p className="text-3xl font-bold text-emerald-700">{tasks.length}</p>
              <p className="text-sm text-emerald-600">Tasks</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-blue-50 to-cyan-50 border-blue-200">
            <CardContent className="pt-6 text-center">
              <Calendar className="w-12 h-12 mx-auto mb-3 text-blue-600" />
              <p className="text-3xl font-bold text-blue-700">{events.length}</p>
              <p className="text-sm text-blue-600">Events</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-amber-50 to-orange-50 border-amber-200">
            <CardContent className="pt-6 text-center">
              <Phone className="w-12 h-12 mx-auto mb-3 text-amber-600" />
              <p className="text-3xl font-bold text-amber-700">{stats.calls_handled}</p>
              <p className="text-sm text-amber-600">Calls</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-violet-50 to-purple-50 border-violet-200">
            <CardContent className="pt-6 text-center">
              <Brain className="w-12 h-12 mx-auto mb-3 text-violet-600" />
              <p className="text-3xl font-bold text-violet-700">{stats.queries_answered}</p>
              <p className="text-sm text-violet-600">Queries</p>
            </CardContent>
          </Card>
          <Card className="bg-gradient-to-br from-rose-50 to-pink-50 border-rose-200">
            <CardContent className="pt-6 text-center">
              <ListTodo className="w-12 h-12 mx-auto mb-3 text-rose-600" />
              <p className="text-3xl font-bold text-rose-700">{stats.tasks_completed}</p>
              <p className="text-sm text-rose-600">Completed</p>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Agent Selector */}
          <div className="lg:col-span-1">
            <Card className="sticky top-4">
              <CardHeader>
                <CardTitle className="text-2xl">🤖 AI Agents</CardTitle>
                <CardDescription>Choose your assistant</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {Object.entries(agentConfig).map(([key, config]) => {
                  const Icon = config.icon;
                  const isActive = activeAgent === key;
                  return (
                    <button
                      key={key}
                      onClick={() => handleAgentSwitch(key)}
                      data-testid={`agent-selector-${key}`}
                      className={`w-full p-4 rounded-xl text-left transition-all hover:scale-105 ${
                        isActive
                          ? `${config.bgColor} ring-2 ring-offset-2 ring-${config.color.split('-')[1]}-400 shadow-lg`
                          : 'bg-slate-50 hover:bg-slate-100'
                      }`}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div className={`p-2 rounded-lg bg-gradient-to-br ${config.color}`}>
                          <Icon className="w-5 h-5 text-white" />
                        </div>
                        <div className="flex-1">
                          <h3 className="font-bold text-slate-800">{config.title}</h3>
                          {isActive && (
                            <Badge variant="secondary" className="text-xs mt-1">Active</Badge>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-slate-600">{config.description}</p>
                    </button>
                  );
                })}
              </CardContent>
            </Card>

            {/* Voice Control */}
            <Card className="mt-4">
              <CardHeader>
                <CardTitle className="text-lg">🎙️ Voice Assistant</CardTitle>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={toggleVoice}
                  data-testid="voice-toggle-button"
                  className={`w-full h-16 text-lg font-bold transition-all ${
                    isListening
                      ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                      : `bg-gradient-to-r ${currentAgent.color} hover:scale-105`
                  }`}
                >
                  {isListening ? (
                    <><MicOff className="mr-2" /> Stop Listening</>
                  ) : (
                    <><Mic className="mr-2" /> Start Voice</>
                  )}
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Chat Interface */}
          <div className="lg:col-span-2">
            <Card className="h-[700px] flex flex-col">
              <CardHeader className={`${currentAgent.bgColor} border-b`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-3 rounded-xl bg-gradient-to-br ${currentAgent.color}`}>
                      <AgentIcon className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <CardTitle className="text-xl">{currentAgent.title}</CardTitle>
                      <CardDescription>{currentAgent.description}</CardDescription>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleClearMessages}
                    data-testid="clear-messages-button"
                    title="Clear conversation"
                  >
                    <Trash2 className="w-5 h-5" />
                  </Button>
                </div>
              </CardHeader>

              {/* Messages */}
              <ScrollArea className="flex-1 p-6">
                {messages.length === 0 ? (
                  <div className="text-center py-12">
                    <div className="text-6xl mb-4">💬</div>
                    <h3 className="text-2xl font-bold text-slate-700 mb-4">Ready to Collaborate!</h3>
                    <p className="text-slate-500 mb-4">Try these examples:</p>
                    <div className="space-y-2">
                      {currentAgent.examples.map((example, i) => (
                        <button
                          key={i}
                          onClick={() => setInputText(example)}
                          className="block w-full max-w-md mx-auto px-4 py-2 text-sm bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex gap-3 ${
                          msg.role === 'user' ? 'flex-row-reverse' : ''
                        }`}
                        data-testid={`message-${msg.role}-${idx}`}
                      >
                        <div
                          className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                            msg.role === 'user'
                              ? 'bg-gradient-to-br from-amber-400 to-orange-500'
                              : `bg-gradient-to-br ${agentConfig[msg.agent].color}`
                          }`}
                        >
                          <span className="text-white text-lg">
                            {msg.role === 'user' ? '👤' : '🤖'}
                          </span>
                        </div>
                        <div
                          className={`flex-1 max-w-2xl px-4 py-3 rounded-2xl ${
                            msg.role === 'user'
                              ? 'bg-gradient-to-r from-amber-100 to-orange-100 text-slate-800'
                              : 'bg-gradient-to-r from-slate-100 to-slate-200 text-slate-800'
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-bold text-sm">
                              {msg.role === 'user' ? 'You' : currentAgent.title}
                            </span>
                            <span className="text-xs text-slate-500">{msg.timestamp}</span>
                          </div>
                          <div className="text-sm whitespace-pre-wrap">{msg.content}</div>
                        </div>
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </ScrollArea>

              {/* Input */}
              <div className="border-t p-4">
                <div className="flex gap-2">
                  <Textarea
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    placeholder={`Ask ${currentAgent.title}...`}
                    data-testid="message-input"
                    className="min-h-[60px] resize-none"
                  />
                  <Button
                    onClick={() => handleSendMessage()}
                    data-testid="send-message-button"
                    className={`bg-gradient-to-r ${currentAgent.color} hover:scale-105`}
                    size="icon"
                  >
                    <Send className="w-5 h-5" />
                  </Button>
                </div>
                <p className="text-xs text-slate-500 mt-2">
                  Press Enter to send, Shift+Enter for new line
                </p>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
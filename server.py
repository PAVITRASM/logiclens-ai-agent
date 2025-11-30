from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import re

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class Task(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    status: str = "pending"
    priority: str = "medium"
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%H:%M %d/%m"))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class TaskCreate(BaseModel):
    title: str
    priority: Optional[str] = "medium"

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None

class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    time: str
    date: str
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%H:%M"))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EventCreate(BaseModel):
    title: str
    time: str
    date: str

class Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user" or "assistant"
    content: str
    agent: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%H:%M"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class MessageCreate(BaseModel):
    content: str
    agent: str

class AgentStats(BaseModel):
    tasks_created: int = 0
    tasks_completed: int = 0
    events_created: int = 0
    calls_handled: int = 0
    queries_answered: int = 0

# Agent Logic Classes
class TaskManagerAgent:
    @staticmethod
    async def process(text: str, db) -> dict:
        text_lower = text.lower()
        
        # Create task
        if any(word in text_lower for word in ["task", "create", "add", "todo", "new task"]):
            task = Task(title=text)
            doc = task.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.tasks.insert_one(doc)
            
            total = await db.tasks.count_documents({})
            return {
                "response": f"🎉 **Task Created Successfully!**\n\n📋 **Title**: {task.title}\n🆔 **ID**: {task.id[:8]}\n⏰ **Created**: {task.created}\n📊 **Status**: 🟡 Pending\n\n💡 **Total Tasks**: {total}",
                "action": "task_created"
            }
        
        # List tasks
        elif any(word in text_lower for word in ["list", "show", "tasks", "my tasks"]):
            tasks = await db.tasks.find({}, {"_id": 0}).sort("timestamp", -1).limit(5).to_list(5)
            
            if not tasks:
                return {
                    "response": "📭 **No tasks yet!** 🎉\n\n💡 Say: 'Create a task to call John'",
                    "action": "list_empty"
                }
            
            task_list = "**📋 Your Recent Tasks:**\n\n"
            for task in tasks:
                status_emoji = "🟢" if task['status'] == 'completed' else "🟡"
                task_list += f"{status_emoji} **{task['id'][:8]}** - {task['title']}\n⏰ {task['created']}\n\n"
            
            total = await db.tasks.count_documents({})
            completed = await db.tasks.count_documents({"status": "completed"})
            task_list += f"📊 **Stats**: {total} Total | {completed} Completed"
            
            return {"response": task_list, "action": "list_tasks"}
        
        # Complete task
        elif any(word in text_lower for word in ["complete", "done", "finish"]):
            task_ids = re.findall(r'[a-f0-9]{8}', text_lower)
            if task_ids:
                completed_count = 0
                for task_id in task_ids:
                    result = await db.tasks.update_many(
                        {"id": {"$regex": f"^{task_id}"}},
                        {"$set": {"status": "completed"}}
                    )
                    completed_count += result.modified_count
                
                if completed_count > 0:
                    return {
                        "response": f"🎉 **{completed_count} task(s) completed!** ✅\n\n💡 Say 'show tasks' to see your updated list",
                        "action": "task_completed"
                    }
            
            return {
                "response": "💡 **To complete a task:**\n\n• 'Complete task {task_id}'\n• 'Done with task {task_id}'",
                "action": "help"
            }
        
        return {
            "response": "📝 **Task Manager Ready!**\n\n💡 **Quick Commands:**\n• 'Create task to call John'\n• 'Show tasks'\n• 'Complete task {id}'\n\n🎯 Let me know what you'd like to do!",
            "action": "help"
        }

class SchedulerAgent:
    @staticmethod
    async def process(text: str, db) -> dict:
        text_lower = text.lower()
        
        # Create event
        if any(word in text_lower for word in ["schedule", "meeting", "appointment", "book"]):
            time_match = re.search(r'at\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_lower)
            hour = 14
            minute = 0
            
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                if time_match.group(3) and time_match.group(3).startswith('p') and hour != 12:
                    hour += 12
                elif time_match.group(3) and time_match.group(3).startswith('a') and hour == 12:
                    hour = 0
            
            event_title = "Meeting"
            if "call" in text_lower:
                event_title = "Call"
            elif "appointment" in text_lower:
                event_title = "Appointment"
            
            event_time = f"{hour:02d}:{minute:02d}"
            event_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%d/%m/%Y")
            
            event = Event(title=event_title, time=event_time, date=event_date)
            doc = event.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            await db.events.insert_one(doc)
            
            total = await db.events.count_documents({})
            return {
                "response": f"📅 **Event Scheduled Successfully!**\n\n🎯 **{event.title}**\n🕐 **Time**: {event.time}\n📅 **Date**: {event.date}\n🆔 **ID**: {event.id[:8]}\n\n📊 **Total Events**: {total}",
                "action": "event_created"
            }
        
        # List events
        elif any(word in text_lower for word in ["show", "calendar", "events", "schedule"]):
            events = await db.events.find({}, {"_id": 0}).sort("timestamp", -1).limit(3).to_list(3)
            
            if not events:
                return {
                    "response": "📅 **No events scheduled!**\n\n💡 Say: 'Schedule meeting at 2 PM'",
                    "action": "list_empty"
                }
            
            event_list = "**📅 Upcoming Events:**\n\n"
            for event in events:
                event_list += f"🆔 **{event['id'][:8]}** - {event['title']} @ {event['time']}\n📅 {event['date']}\n\n"
            
            total = await db.events.count_documents({})
            event_list += f"📊 **Total**: {total} events"
            
            return {"response": event_list, "action": "list_events"}
        
        return {
            "response": "📅 **Smart Scheduler Ready!**\n\n💡 **Quick Commands:**\n• 'Schedule meeting at 3 PM'\n• 'Book call at 10 AM'\n• 'Show calendar'\n\n🎯 How can I help you schedule?",
            "action": "help"
        }

class ReceptionAgent:
    @staticmethod
    async def process(text: str, db) -> dict:
        text_lower = text.lower()
        
        greetings = ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"]
        if any(g in text_lower for g in greetings):
            return {
                "response": "👋 **Welcome to LogicLens AI!**\n\n🎉 I'm your 24/7 virtual receptionist\n\n💡 **How can I help you today?**\n• Connect you to an agent\n• Schedule a meeting\n• Take a message\n• Answer company questions",
                "action": "greeting"
            }
        
        if any(word in text_lower for word in ["call", "phone", "contact", "transfer"]):
            return {
                "response": "📞 **Call Handling Active**\n\n👤 **Who would you like to reach?**\n\n🔗 **Available Options:**\n• 💼 Sales Team\n• 🛠️ Support Team\n• 📊 Management\n• 📅 Scheduling\n\n💡 Say: 'Connect me to sales' or 'I need support'",
                "action": "call_routing"
            }
        
        if any(word in text_lower for word in ["support", "help", "issue", "problem"]):
            return {
                "response": "🆘 **Support Team Ready!**\n\n🔍 **Common Issues:**\n• Login problems\n• Feature questions\n• Technical errors\n• Billing inquiries\n\n📝 **Please describe your issue**\nI'll connect you to the right specialist!",
                "action": "support"
            }
        
        return {
            "response": "👋 **Thank you for calling LogicLens AI!**\n\n🤖 **Professional Receptionist**\n📅 **Available 24/7**\n⚡ **Instant Response**\n\n💡 **Popular requests:**\n• Connect to department\n• Schedule meeting\n• Take message\n• Company info",
            "action": "help"
        }

class KnowledgeBaseAgent:
    @staticmethod
    async def process(text: str, db) -> dict:
        text_lower = text.lower()
        
        knowledge_base = {
            "company": "🏢 **LogicLens AI - Company Overview**\n\n🚀 **What we do:**\n• Multi-Agent AI Platform\n• Business Automation\n• 24/7 Intelligent Operations\n\n📊 **Key Features:**\n• 4 Specialized AI Agents\n• Voice-Powered Interface\n• Real-time Task Management\n• Smart Scheduling System",
            
            "features": "✨ **LogicLens AI Features**\n\n🤖 **4 Powerful Agents:**\n\n✅ **Task Manager** - Create & track tasks\n📅 **Scheduler** - Meeting automation\n📞 **Reception** - 24/7 call handling\n🧠 **Knowledge Base** - Instant answers\n\n🎙️ **Voice Interface**\n• Natural speech recognition\n• Real-time responses\n• Multi-language support",
            
            "pricing": "💰 **Pricing Plans**\n\n💎 **Free** - $0/mo\nBasic agents, 100 interactions\n\n🚀 **Pro** - $29/mo\nUnlimited agents, Voice, Analytics\n\n🏢 **Enterprise** - Custom\nWhite-label, API, Priority support\n\n🎁 **14-day free trial** for all plans!",
            
            "support": "🆘 **Support & Contact**\n\n📞 **24/7 Support Channels:**\n• ☎️ Phone: +1-800-LOGICLENS\n• 💬 Live Chat: Available now\n• 📧 Email: support@logiclens.ai\n• 🤖 AI Assistant: You're talking to me!\n\n⏱️ **Response Times:**\n• Critical: <5 minutes\n• Standard: <1 hour\n• General: <4 hours"
        }
        
        for key, response in knowledge_base.items():
            if key in text_lower:
                return {"response": response, "action": "knowledge"}
        
        if any(word in text_lower for word in ["price", "cost", "plan"]):
            return {"response": knowledge_base["pricing"], "action": "knowledge"}
        if any(word in text_lower for word in ["help", "support", "contact"]):
            return {"response": knowledge_base["support"], "action": "knowledge"}
        if "feature" in text_lower:
            return {"response": knowledge_base["features"], "action": "knowledge"}
        
        return {
            "response": f"🧠 **Knowledge Base Search**\n\n🔍 **Searching for**: \"{text}\"\n\n💡 **Popular Topics:**\n• 'Company information'\n• 'Features and capabilities'\n• 'Pricing plans'\n• 'Support contact'",
            "action": "search"
        }

# API Routes
@api_router.get("/")
async def root():
    return {"message": "LogicLens AI API"}

# Tasks
@api_router.post("/tasks", response_model=Task)
async def create_task(task: TaskCreate):
    new_task = Task(title=task.title, priority=task.priority)
    doc = new_task.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.tasks.insert_one(doc)
    return new_task

@api_router.get("/tasks", response_model=List[Task])
async def get_tasks():
    tasks = await db.tasks.find({}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    for task in tasks:
        if isinstance(task.get('timestamp'), str):
            task['timestamp'] = datetime.fromisoformat(task['timestamp'])
    return tasks

@api_router.patch("/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdate):
    update_dict = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_dict:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    result = await db.tasks.update_one(
        {"id": task_id},
        {"$set": update_dict}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task updated successfully"}

@api_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    result = await db.tasks.delete_one({"id": task_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}

# Events
@api_router.post("/events", response_model=Event)
async def create_event(event: EventCreate):
    new_event = Event(title=event.title, time=event.time, date=event.date)
    doc = new_event.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.events.insert_one(doc)
    return new_event

@api_router.get("/events", response_model=List[Event])
async def get_events():
    events = await db.events.find({}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    for event in events:
        if isinstance(event.get('timestamp'), str):
            event['timestamp'] = datetime.fromisoformat(event['timestamp'])
    return events

@api_router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    result = await db.events.delete_one({"id": event_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"message": "Event deleted successfully"}

# Messages
@api_router.post("/messages")
async def process_message(message: MessageCreate):
    # Save user message
    user_msg = Message(role="user", content=message.content, agent=message.agent)
    user_doc = user_msg.model_dump()
    user_doc['created_at'] = user_doc['created_at'].isoformat()
    await db.messages.insert_one(user_doc)
    
    # Process with agent
    agents = {
        'task_manager': TaskManagerAgent,
        'scheduler': SchedulerAgent,
        'reception': ReceptionAgent,
        'knowledge_base': KnowledgeBaseAgent
    }
    
    agent_class = agents.get(message.agent)
    if not agent_class:
        raise HTTPException(status_code=400, detail="Invalid agent")
    
    result = await agent_class.process(message.content, db)
    
    # Save assistant response
    assistant_msg = Message(role="assistant", content=result["response"], agent=message.agent)
    assistant_doc = assistant_msg.model_dump()
    assistant_doc['created_at'] = assistant_doc['created_at'].isoformat()
    await db.messages.insert_one(assistant_doc)
    
    # Update stats
    if message.agent == 'task_manager' and result.get('action') == 'task_created':
        await db.stats.update_one({}, {"$inc": {"tasks_created": 1}}, upsert=True)
    elif message.agent == 'task_manager' and result.get('action') == 'task_completed':
        await db.stats.update_one({}, {"$inc": {"tasks_completed": 1}}, upsert=True)
    elif message.agent == 'scheduler' and result.get('action') == 'event_created':
        await db.stats.update_one({}, {"$inc": {"events_created": 1}}, upsert=True)
    elif message.agent == 'reception':
        await db.stats.update_one({}, {"$inc": {"calls_handled": 1}}, upsert=True)
    elif message.agent == 'knowledge_base':
        await db.stats.update_one({}, {"$inc": {"queries_answered": 1}}, upsert=True)
    
    return {
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "action": result.get("action")
    }

@api_router.get("/messages")
async def get_messages(agent: Optional[str] = None, limit: int = 50):
    query = {"agent": agent} if agent else {}
    messages = await db.messages.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    for msg in messages:
        if isinstance(msg.get('created_at'), str):
            msg['created_at'] = datetime.fromisoformat(msg['created_at'])
    return list(reversed(messages))

@api_router.delete("/messages")
async def clear_messages():
    await db.messages.delete_many({})
    return {"message": "All messages cleared"}

# Stats
@api_router.get("/stats", response_model=AgentStats)
async def get_stats():
    stats = await db.stats.find_one({}, {"_id": 0})
    if not stats:
        return AgentStats()
    return AgentStats(**stats)

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
/**
 * DAY 34: React Native Mobile App Setup
 * =========================================
 * Single-file mobile client for the AI Chatbot platform.
 * Connects to the existing REST API (api.py) for auth + chat.
 *
 * Setup:
 *   npx react-native init AIChatbotMobile
 *   (or) npx create-expo-app AIChatbotMobile
 *   Replace App.js with this file
 *   npm install @react-native-async-storage/async-storage
 *   npx expo start   (or) npx react-native run-android / run-ios
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  SafeAreaView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Alert,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// ---------------- CONFIG ----------------
const API_BASE_URL = 'https://murthu-chatbot-api.onrender.com/api/v1'; // live deployed API

// ---------------- API HELPERS ----------------
async function apiRequest(endpoint, method = 'GET', body = null, token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(err.error || `HTTP ${response.status}`);
  }
  return response.json();
}

// ---------------- LOGIN SCREEN ----------------
function LoginScreen({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!username || !password) {
      Alert.alert('Missing fields', 'Enter username and password');
      return;
    }
    setLoading(true);
    try {
      const data = await apiRequest('/auth/login', 'POST', { username, password });
      await AsyncStorage.setItem('auth_token', data.token);
      await AsyncStorage.setItem('user_id', String(data.user_id));
      onLoginSuccess(data.token, data.user_id);
    } catch (e) {
      Alert.alert('Login failed', e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.centeredContainer}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.logo}>🤖 AI Chatbot</Text>
      <Text style={styles.subtitle}>Day 34 · Mobile Setup</Text>

      <TextInput
        style={styles.input}
        placeholder="Username"
        placeholderTextColor="#888"
        value={username}
        onChangeText={setUsername}
        autoCapitalize="none"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor="#888"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <TouchableOpacity style={styles.primaryButton} onPress={handleLogin} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryButtonText}>Login</Text>}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

// ---------------- CHAT LIST SCREEN ----------------
function ChatListScreen({ token, userId, onOpenChat, onLogout }) {
  const [chats, setChats] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadChats = useCallback(async () => {
    try {
      const data = await apiRequest(`/chats/${userId}`, 'GET', null, token);
      setChats(data.chats || []);
    } catch (e) {
      Alert.alert('Error loading chats', e.message);
    } finally {
      setLoading(false);
    }
  }, [token, userId]);

  useEffect(() => {
    loadChats();
  }, [loadChats]);

  if (loading) {
    return (
      <View style={styles.centeredContainer}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.headerTitle}>💬 Your Chats</Text>
        <TouchableOpacity onPress={onLogout}>
          <Text style={styles.logoutText}>Logout</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={chats}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ padding: 16 }}
        renderItem={({ item }) => (
          <TouchableOpacity style={styles.chatCard} onPress={() => onOpenChat(item.id, item.title)}>
            <Text style={styles.chatTitle}>{item.title}</Text>
            <Text style={styles.chatMeta}>{item.personality || 'default'} · {item.created_at}</Text>
          </TouchableOpacity>
        )}
        ListEmptyComponent={<Text style={styles.emptyText}>No chats yet. Start a new one!</Text>}
      />
    </SafeAreaView>
  );
}

// ---------------- CHAT SCREEN ----------------
function ChatScreen({ token, chatId, chatTitle, onBack }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [botTyping, setBotTyping] = useState(false);
  const listRef = React.useRef(null);

  const loadMessages = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const data = await apiRequest(`/chat/${chatId}/messages`, 'GET', null, token);
      setMessages(data.messages || []);
    } catch (e) {
      Alert.alert('Error loading messages', e.message);
    } finally {
      if (isRefresh) setRefreshing(false);
    }
  }, [chatId, token]);

  useEffect(() => {
    loadMessages();
  }, [loadMessages]);

  const scrollToBottom = () => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
  };

  const sendMessage = async () => {
    if (!input.trim()) return;
    const text = input.trim();
    setInput('');
    setSending(true);
    setBotTyping(true);
    setMessages((prev) => [...prev, { role: 'user', content: text, timestamp: new Date().toISOString() }]);
    scrollToBottom();

    try {
      const data = await apiRequest(`/chat/${chatId}/messages`, 'POST', { content: text }, token);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply, timestamp: new Date().toISOString() }]);
    } catch (e) {
      Alert.alert('Send failed', e.message);
    } finally {
      setSending(false);
      setBotTyping(false);
      scrollToBottom();
    }
  };

  const formatTime = (ts) => {
    if (!ts) return '';
    try {
      return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={onBack}><Text style={styles.backText}>← Back</Text></TouchableOpacity>
        <Text style={styles.headerTitle} numberOfLines={1}>{chatTitle}</Text>
        <View style={{ width: 50 }} />
      </View>

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(_, i) => String(i)}
        contentContainerStyle={{ padding: 16 }}
        onContentSizeChange={scrollToBottom}
        refreshing={refreshing}
        onRefresh={() => loadMessages(true)}
        renderItem={({ item }) => (
          <View style={[styles.bubble, item.role === 'user' ? styles.bubbleUser : styles.bubbleBot]}>
            <Text style={styles.bubbleText}>{item.content}</Text>
            {!!item.timestamp && <Text style={styles.bubbleTime}>{formatTime(item.timestamp)}</Text>}
          </View>
        )}
        ListFooterComponent={
          botTyping ? (
            <View style={[styles.bubble, styles.bubbleBot, styles.bubbleTyping]}>
              <ActivityIndicator size="small" color="#8B5CF6" />
              <Text style={[styles.bubbleText, { marginLeft: 8 }]}>typing…</Text>
            </View>
          ) : null
        }
      />

      <View style={styles.inputRow}>
        <TextInput
          style={styles.chatInput}
          placeholder="Type your message..."
          placeholderTextColor="#888"
          value={input}
          onChangeText={setInput}
          onSubmitEditing={sendMessage}
          returnKeyType="send"
          multiline
        />
        <TouchableOpacity style={styles.sendButton} onPress={sendMessage} disabled={sending || !input.trim()}>
          {sending ? <ActivityIndicator color="#fff" size="small" /> : <Text style={styles.sendButtonText}>➤</Text>}
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

// ---------------- ROOT APP (navigation state machine) ----------------
export default function App() {
  const [token, setToken] = useState(null);
  const [userId, setUserId] = useState(null);
  const [screen, setScreen] = useState('login'); // login -> chatList -> chat
  const [activeChat, setActiveChat] = useState(null);
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    (async () => {
      const savedToken = await AsyncStorage.getItem('auth_token');
      const savedUserId = await AsyncStorage.getItem('user_id');
      if (savedToken) {
        setToken(savedToken);
        setUserId(savedUserId);
        setScreen('chatList');
      }
      setBooting(false);
    })();
  }, []);

  const handleLogout = async () => {
    await AsyncStorage.multiRemove(['auth_token', 'user_id']);
    setToken(null);
    setUserId(null);
    setScreen('login');
  };

  if (booting) {
    return (
      <View style={styles.centeredContainer}>
        <ActivityIndicator size="large" color="#6366F1" />
      </View>
    );
  }

  if (screen === 'login') {
    return (
      <LoginScreen
        onLoginSuccess={(t, uid) => {
          setToken(t);
          setUserId(uid);
          setScreen('chatList');
        }}
      />
    );
  }

  if (screen === 'chat') {
    return (
      <ChatScreen
        token={token}
        chatId={activeChat.id}
        chatTitle={activeChat.title}
        onBack={() => setScreen('chatList')}
      />
    );
  }

  return (
    <ChatListScreen
      token={token}
      userId={userId}
      onOpenChat={(id, title) => {
        setActiveChat({ id, title });
        setScreen('chat');
      }}
      onLogout={handleLogout}
    />
  );
}

// ---------------- STYLES ----------------
const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0F0F1A' },
  centeredContainer: { flex: 1, backgroundColor: '#0F0F1A', justifyContent: 'center', alignItems: 'center', padding: 24 },
  logo: { fontSize: 32, fontWeight: '700', color: '#fff', marginBottom: 4 },
  subtitle: { fontSize: 14, color: '#8B5CF6', marginBottom: 32 },
  input: {
    width: '100%', backgroundColor: '#1C1C2E', borderRadius: 12, padding: 14,
    color: '#fff', marginBottom: 12, borderWidth: 1, borderColor: '#2A2A40',
  },
  primaryButton: {
    width: '100%', backgroundColor: '#6366F1', borderRadius: 12, padding: 14,
    alignItems: 'center', marginTop: 8,
  },
  primaryButtonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  headerRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 16, borderBottomWidth: 1, borderBottomColor: '#2A2A40',
  },
  headerTitle: { color: '#fff', fontSize: 18, fontWeight: '700', flex: 1, textAlign: 'center' },
  logoutText: { color: '#EF4444', fontWeight: '600' },
  backText: { color: '#8B5CF6', fontWeight: '600', width: 50 },
  chatCard: { backgroundColor: '#1C1C2E', borderRadius: 12, padding: 16, marginBottom: 10 },
  chatTitle: { color: '#fff', fontSize: 16, fontWeight: '600' },
  chatMeta: { color: '#888', fontSize: 12, marginTop: 4 },
  emptyText: { color: '#888', textAlign: 'center', marginTop: 40 },
  bubble: { maxWidth: '80%', borderRadius: 14, padding: 12, marginBottom: 10 },
  bubbleUser: { backgroundColor: '#6366F1', alignSelf: 'flex-end' },
  bubbleBot: { backgroundColor: '#1C1C2E', alignSelf: 'flex-start' },
  bubbleText: { color: '#fff' },
  bubbleTime: { color: 'rgba(255,255,255,0.5)', fontSize: 10, marginTop: 4, alignSelf: 'flex-end' },
  bubbleTyping: { flexDirection: 'row', alignItems: 'center' },
  inputRow: { flexDirection: 'row', padding: 12, borderTopWidth: 1, borderTopColor: '#2A2A40' },
  chatInput: { flex: 1, backgroundColor: '#1C1C2E', borderRadius: 20, paddingHorizontal: 16, color: '#fff', marginRight: 8 },
  sendButton: { backgroundColor: '#6366F1', borderRadius: 20, width: 44, height: 44, justifyContent: 'center', alignItems: 'center' },
  sendButtonText: { color: '#fff', fontSize: 18, fontWeight: '700' },
});

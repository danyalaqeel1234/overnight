import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ScrollView,
  TextInput,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface CoStreamScreenProps {
  sessionId: string;
  onBack: () => void;
}

export const CoStreamScreen: React.FC<CoStreamScreenProps> = ({
  sessionId,
  onBack,
}) => {
  const [chatText, setChatText] = useState('');
  const [messages, setMessages] = useState<Array<{ id: string; sender: string; text: string }>>([
    { id: '1', sender: 'Host', text: 'Welcome to synchronized co-stream session!' },
  ]);

  const handleSendChat = () => {
    if (!chatText.trim()) return;
    setMessages((prev) => [
      ...prev,
      { id: String(Date.now()), sender: 'You', text: chatText.trim() },
    ]);
    setChatText('');
  };

  return (
    <View style={styles.screenWrapper} testID="costream-screen" accessibilityLabel="costream-screen">
      {/* Top Bar */}
      <View style={styles.navBar}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={onBack}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Back"
        >
          <Ionicons name="arrow-back" size={22} color="#0F172A" />
        </TouchableOpacity>
        <View style={styles.navTitleContainer}>
          <Text style={styles.navTitle}>Co-Stream Live</Text>
          <Text style={styles.navSubtitle}>{sessionId}</Text>
        </View>
        <View style={{ width: 48 }} />
      </View>

      {/* Video Composite Area */}
      <View style={styles.videoPlayerBox}>
        <Ionicons name="videocam" size={48} color="#94A3B8" />
        <Text style={styles.videoText}>Synchronized 4-Way Co-Stream</Text>
        <Text style={styles.videoSubtext}>Composite Playback: http://localhost:8888/costream/{sessionId}/index.m3u8</Text>
      </View>

      {/* Chat Area */}
      <View style={styles.chatSection}>
        <Text style={styles.chatHeader}>Co-Stream Room: chat-{sessionId}</Text>
        <ScrollView style={styles.chatList} contentContainerStyle={{ padding: 8 }}>
          {messages.map((m) => (
            <View key={m.id} style={styles.chatMessage}>
              <Text style={styles.chatSender}>{m.sender}:</Text>
              <Text style={styles.chatMsgText}>{m.text}</Text>
            </View>
          ))}
        </ScrollView>
        <View style={styles.chatInputRow}>
          <TextInput
            style={styles.chatInput}
            value={chatText}
            onChangeText={setChatText}
            placeholder="Send reaction..."
            placeholderTextColor="#94A3B8"
          />
          <TouchableOpacity style={styles.sendButton} onPress={handleSendChat}>
            <Ionicons name="send" size={18} color="#FFFFFF" />
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  screenWrapper: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  navBar: {
    height: 56,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    backgroundColor: '#1E293B',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#F1F5F9',
    justifyContent: 'center',
    alignItems: 'center',
  },
  navTitleContainer: {
    alignItems: 'center',
  },
  navTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#F8FAFC',
  },
  navSubtitle: {
    fontSize: 12,
    color: '#94A3B8',
  },
  videoPlayerBox: {
    width: '100%',
    aspectRatio: 16 / 9,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#334155',
  },
  videoText: {
    color: '#F8FAFC',
    fontSize: 15,
    fontWeight: '600',
    marginTop: 8,
  },
  videoSubtext: {
    color: '#64748B',
    fontSize: 11,
    marginTop: 4,
    paddingHorizontal: 20,
    textAlign: 'center',
  },
  chatSection: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  chatHeader: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
    borderBottomWidth: 1,
    borderBottomColor: '#1E293B',
  },
  chatList: {
    flex: 1,
  },
  chatMessage: {
    flexDirection: 'row',
    marginBottom: 6,
  },
  chatSender: {
    fontWeight: '700',
    color: '#38BDF8',
    marginRight: 6,
    fontSize: 13,
  },
  chatMsgText: {
    color: '#F1F5F9',
    fontSize: 13,
    flexShrink: 1,
  },
  chatInputRow: {
    flexDirection: 'row',
    padding: 12,
    backgroundColor: '#1E293B',
    alignItems: 'center',
  },
  chatInput: {
    flex: 1,
    backgroundColor: '#0F172A',
    borderRadius: 20,
    paddingHorizontal: 16,
    height: 40,
    color: '#F8FAFC',
    fontSize: 14,
    marginRight: 8,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#2563EB',
    justifyContent: 'center',
    alignItems: 'center',
  },
});

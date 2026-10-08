import { Link, useLocalSearchParams } from "expo-router";
import { ScrollView, Text } from "react-native";

import { noteById } from "@/lib/notes";

export default function NoteDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const note = noteById(id);

  if (!note) {
    return (
      <ScrollView contentContainerStyle={{ padding: 24 }}>
        <Text>Note not found.</Text>
        <Link href="/">Back to Home</Link>
      </ScrollView>
    );
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 24, gap: 12 }}>
      <Text style={{ fontSize: 28, fontWeight: "700" }}>{note.title}</Text>
      <Text>{note.author} · {note.observedAt}</Text>
      <Text>{note.body}</Text>
      <Text>{note.tags.map((tag) => `#${tag}`).join(" ")}</Text>
    </ScrollView>
  );
}

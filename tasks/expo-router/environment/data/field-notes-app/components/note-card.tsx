import { Link } from "expo-router";
import { Pressable, Text, View } from "react-native";

import type { FieldNote } from "@/lib/notes";

export function NoteCard({ note }: { note: FieldNote }) {
  return (
    <Link href={{ pathname: "/notes/[id]", params: { id: note.id } }} asChild>
      <Pressable accessibilityRole="button">
        <View style={{ padding: 16, gap: 6 }}>
          <Text style={{ fontSize: 18, fontWeight: "600" }}>{note.title}</Text>
          <Text numberOfLines={2}>{note.body}</Text>
          <Text>{note.author} · {note.observedAt}</Text>
        </View>
      </Pressable>
    </Link>
  );
}

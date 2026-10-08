import { FlatList, Text, View } from "react-native";

import { NoteCard } from "@/components/note-card";
import type { FieldNote } from "@/lib/notes";

export function NoteList({ notes, emptyMessage }: { notes: FieldNote[]; emptyMessage: string }) {
  return (
    <FlatList
      data={notes}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <NoteCard note={item} />}
      ListEmptyComponent={
        <View style={{ padding: 24 }}>
          <Text>{emptyMessage}</Text>
        </View>
      }
    />
  );
}

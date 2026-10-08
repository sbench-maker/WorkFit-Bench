import { useMemo, useState } from "react";
import { TextInput, View } from "react-native";

import { NoteList } from "@/components/note-list";
import { filterNotes, notesNewestFirst } from "@/lib/notes";

export default function SearchScreen() {
  const [query, setQuery] = useState("");
  const matches = useMemo(() => filterNotes(notesNewestFirst, query), [query]);

  return (
    <View style={{ flex: 1 }}>
      <TextInput
        accessibilityLabel="Search field notes"
        onChangeText={setQuery}
        placeholder="Search notes"
        value={query}
      />
      <NoteList notes={matches} emptyMessage={`No notes found for “${query.trim()}”.`} />
    </View>
  );
}

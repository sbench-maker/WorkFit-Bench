import { NoteList } from "@/components/note-list";
import { notesNewestFirst } from "@/lib/notes";

export default function HomeScreen() {
  return <NoteList notes={notesNewestFirst} emptyMessage="No field notes yet." />;
}

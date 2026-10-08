import { NoteList } from "@/components/note-list";
import { savedNotes } from "@/lib/notes";

export default function SavedScreen() {
  return <NoteList notes={savedNotes} emptyMessage="No saved notes." />;
}

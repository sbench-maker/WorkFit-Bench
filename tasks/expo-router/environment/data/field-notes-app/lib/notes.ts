import noteRecords from "@/data/notes.json";

export type FieldNote = {
  id: string;
  title: string;
  body: string;
  author: string;
  observedAt: string;
  tags: string[];
  saved: boolean;
};

export const notesNewestFirst = (noteRecords as FieldNote[]).slice().sort((a, b) =>
  b.observedAt.localeCompare(a.observedAt),
);

export const savedNotes = notesNewestFirst.filter((note) => note.saved);

export function noteById(id: string | undefined) {
  return notesNewestFirst.find((note) => note.id === id);
}

export function filterNotes(notes: FieldNote[], rawQuery: string) {
  const query = rawQuery.trim().toLocaleLowerCase();
  if (!query) return notes;

  return notes.filter((note) =>
    [note.title, note.body, note.author, ...note.tags]
      .join(" ")
      .toLocaleLowerCase()
      .includes(query),
  );
}

const rpeEmojis: Record<number, string> = {
  1: "😄",
  2: "🙂",
  3: "🙂",
  4: "😐",
  5: "😐",
  6: "😟",
  7: "😣",
  8: "😫",
  9: "🥵",
  10: "😵",
};

export function rpeOptionLabel(value: number) {
  return `${rpeEmojis[value] ?? "😐"} ${value}`;
}

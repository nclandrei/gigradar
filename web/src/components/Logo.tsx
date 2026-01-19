import Image from "next/image";
import Link from "next/link";

export function Logo() {
  return (
    <Link href="/" className="group flex items-center gap-3">
      <Image
        src="/logo.png"
        alt="Cultură la plic"
        width={48}
        height={48}
        className="rounded-base border-2 border-border"
      />
      <span className="relative text-3xl md:text-5xl font-bold tracking-tight leading-none">
        Cultură la plic
        <span className="absolute -bottom-1 left-0 w-0 h-3 bg-culture -rotate-1 group-hover:w-full transition-all duration-300" />
      </span>
    </Link>
  );
}

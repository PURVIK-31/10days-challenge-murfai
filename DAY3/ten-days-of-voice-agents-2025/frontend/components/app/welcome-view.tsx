import { Button } from '@/components/livekit/button';

function WelcomeImage() {
  return (
    <svg
      width="64"
      height="64"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="text-fg0 mb-4 size-16"
    >
      {/* Wellness lotus/heart icon */}
      <path
        d="M32 8C32 8 20 14 20 26C20 32 24 36 28 38C28 38 26 42 26 46C26 52 32 56 32 56C32 56 38 52 38 46C38 42 36 38 36 38C40 36 44 32 44 26C44 14 32 8 32 8Z"
        fill="currentColor"
        opacity="0.3"
      />
      <path
        d="M32 12C28 12 24 16 24 22C24 26 26 28 28 30C28 30 26 32 26 36C26 40 28 44 32 44C36 44 38 40 38 36C38 32 36 30 36 30C38 28 40 26 40 22C40 16 36 12 32 12Z"
        fill="currentColor"
      />
      <circle cx="32" cy="32" r="3" fill="currentColor" opacity="0.6" />
      <path
        d="M20 32C20 32 16 28 12 28C8 28 6 30 6 34C6 38 10 42 14 42C18 42 20 38 20 34C20 34 20 32 20 32Z"
        fill="currentColor"
        opacity="0.4"
      />
      <path
        d="M44 32C44 32 48 28 52 28C56 28 58 30 58 34C58 38 54 42 50 42C46 42 44 38 44 34C44 34 44 32 44 32Z"
        fill="currentColor"
        opacity="0.4"
      />
    </svg>
  );
}

interface WelcomeViewProps {
  startButtonText: string;
  onStartCall: () => void;
}

export const WelcomeView = ({
  startButtonText,
  onStartCall,
  ref,
}: React.ComponentProps<'div'> & WelcomeViewProps) => {
  return (
    <div ref={ref}>
      <section className="bg-background flex flex-col items-center justify-center text-center">
        <WelcomeImage />

        <p className="text-foreground max-w-prose pt-1 leading-6 font-medium">
          Your daily wellness check-in companion
        </p>
        <p className="text-muted-foreground max-w-prose pt-2 text-sm leading-5">
          A supportive space to reflect on your mood, set intentions, and receive gentle guidance
        </p>

        <Button variant="primary" size="lg" onClick={onStartCall} className="mt-6 w-64 font-mono">
          {startButtonText}
        </Button>
      </section>

      <div className="fixed bottom-5 left-0 flex w-full items-center justify-center">
        <p className="text-muted-foreground max-w-prose pt-1 text-xs leading-5 font-normal text-pretty md:text-sm">
          Take a moment for yourself. Your well-being matters.
        </p>
      </div>
    </div>
  );
};

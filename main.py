import pygame
import random
import sys
import math

# --- Configuration & Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Player physics (time-based, unit: pixels/second^2)
GRAVITY_ACCEL = 1700.0
FLAP_IMPULSE = -470.0
MAX_FALL_SPEED = 750.0
MAX_RISE_SPEED = -520.0
FLAP_STATE_DURATION_MS = 120

# Animation timing (milliseconds)
IDLE_ANIM_INTERVAL_MS = 180
ACTIVE_ANIM_INTERVAL_MS = 90
COIN_ANIM_INTERVAL_MS = 90
COLLECTIBLE_SCORE = 5

# Obstacle/collectible spawn tuning
OBSTACLE_SPAWN_INTERVAL_MS = 1600
OBSTACLE_WIDTH = 70

# Extension tuning (Requirement 5)
DYNAMIC_OBSTACLE_MIN_AMPLITUDE = 25
DYNAMIC_OBSTACLE_MAX_AMPLITUDE = 95
DYNAMIC_OBSTACLE_MIN_ANGULAR_SPEED = 1.2
DYNAMIC_OBSTACLE_MAX_ANGULAR_SPEED = 2.4

PARTICLE_SPAWN_PER_FLAP = 8
PARTICLE_LIFETIME_MS = 320

DIFFICULTY_RAMP_PER_SEC = 0.08
MAX_DIFFICULTY_MULTIPLIER = 2.2
MIN_GAP_SIZE = 125
MAX_GAP_SIZE = 250

# --- Asset placeholders (replace these with your final image files) ---
LAYER1_IMAGE = "assets/sky.png"
LAYER2_IMAGE = "assets/mountains.jpg"
LAYER3_IMAGE = "assets/ground.jpg"

# Player sprite placeholders (replace with your own files later)
PLAYER_IDLE_FRAME_PATHS = [
    "assets/bird/PNG/frame-3.png",
    "assets/bird/PNG/frame-4.png",
]
PLAYER_ACTIVE_FRAME_PATHS = [
    "assets/bird/PNG/frame-1.png",
    "assets/bird/PNG/frame-2.png",
    "assets/bird/PNG/frame-3.png",
]

# Obstacle & collectible placeholders (replace with your own files later)
OBSTACLE_IMAGE = "flappy-bird-assets/sprites/pipe-green.png"
COLLECTIBLE_FRAME_PATHS = [
    "assets/star-coin-rotate/star-coin-rotate-1.png",
    "assets/star-coin-rotate/star-coin-rotate-2.png",
    "assets/star-coin-rotate/star-coin-rotate-3.png",
    "assets/star-coin-rotate/star-coin-rotate-4.png",
    "assets/star-coin-rotate/star-coin-rotate-5.png",
    "assets/star-coin-rotate/star-coin-rotate-6.png"
]

# States
STATE_MENU = "MENU"
STATE_PLAYING = "PLAYING"
STATE_GAMEOVER = "GAMEOVER"
STATE_SETTINGS = "SETTINGS"

class Button:
    """Simple UI Button for Start, Restart, and Settings."""
    def __init__(self, text, x, y, width, height, color, hover_color):
        self.text = text
        self.rect = pygame.Rect(x, y, width, height)
        self.color = color
        self.hover_color = hover_color
        self.font = pygame.font.SysFont("Arial", 30)

    def draw(self, screen):
        mouse_pos = pygame.mouse.get_pos()
        current_color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.color
        pygame.draw.rect(screen, current_color, self.rect, border_radius=10)
        
        text_surf = self.font.render(self.text, True, (255, 255, 255))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

    def is_clicked(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                return True
        return False

class BackgroundLayer:
    def __init__(self, image_path, speed_multiplier, y_pos, height, fallback_color):
        self.speed_multiplier = speed_multiplier
        self.y_pos = y_pos
        self.height = height

        try:
            # Keep original width relation so texture can tile naturally.
            raw_image = pygame.image.load(image_path).convert_alpha()
            raw_w, raw_h = raw_image.get_size()
            scaled_w = max(1, int(raw_w * (height / raw_h)))
            self.image = pygame.transform.smoothscale(raw_image, (scaled_w, height))
        except pygame.error as e:
            print(f"Unable to load image: {image_path} - {e}")
            # Fallback keeps the game running before assets are added.
            self.image = pygame.Surface((SCREEN_WIDTH, height), pygame.SRCALPHA)
            self.image.fill(fallback_color)

        self.width = self.image.get_width()

        # If an imported texture is very narrow, scale up once to reduce repeated seams.
        if self.width < SCREEN_WIDTH // 2:
            self.image = pygame.transform.smoothscale(self.image, (SCREEN_WIDTH // 2, height))
            self.width = self.image.get_width()

        self.offset = 0.0

    def update(self, global_speed):
        move_speed = global_speed * self.speed_multiplier
        self.offset = (self.offset + move_speed) % self.width

    def draw(self, screen):
        start_x = -int(self.offset)
        x = start_x

        # Tile enough copies so the whole screen is always covered.
        while x < SCREEN_WIDTH:
            screen.blit(self.image, (x, self.y_pos))
            x += self.width

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.idle_frames = self._load_frames(PLAYER_IDLE_FRAME_PATHS, [(240, 110, 110), (220, 110, 110)])
        self.active_frames = self._load_frames(PLAYER_ACTIVE_FRAME_PATHS, [(255, 80, 80), (255, 100, 80), (255, 120, 80)])

        self.state = "idle"
        self.current_frames = self.idle_frames
        self.frame_index = 0
        self.image = self.current_frames[self.frame_index]
        self.rect = self.image.get_rect(center=(150, 300))
        self.y = float(self.rect.y)

        # Vertical speed (pixels/second).
        self.velocity_y = 0.0
        self.anim_timer_ms = 0
        self.flap_state_timer_ms = 0

    def _load_frames(self, image_paths, fallback_colors):
        frames = []
        for i, path in enumerate(image_paths):
            try:
                image = pygame.image.load(path).convert_alpha()
                image = pygame.transform.smoothscale(image, (40, 30))
                frames.append(image)
            except pygame.error:
                fallback = pygame.Surface((40, 30), pygame.SRCALPHA)
                fallback.fill(fallback_colors[i % len(fallback_colors)])
                frames.append(fallback)
        return frames

    def _set_state(self, new_state):
        if new_state == self.state:
            return

        self.state = new_state
        self.current_frames = self.active_frames if self.state == "active" else self.idle_frames
        self.frame_index = 0
        self.image = self.current_frames[self.frame_index]

    def _update_animation(self, dt_ms):
        self.anim_timer_ms += dt_ms
        interval = ACTIVE_ANIM_INTERVAL_MS if self.state == "active" else IDLE_ANIM_INTERVAL_MS
        while self.anim_timer_ms >= interval:
            self.anim_timer_ms -= interval
            self.frame_index = (self.frame_index + 1) % len(self.current_frames)
            self.image = self.current_frames[self.frame_index]

    def update(self, dt_ms, flap_requested):
        dt_sec = dt_ms / 1000.0

        # Tap to Flap: each input gives a single upward impulse.
        if flap_requested:
            self.velocity_y = FLAP_IMPULSE
            self.flap_state_timer_ms = FLAP_STATE_DURATION_MS

        self.velocity_y += GRAVITY_ACCEL * dt_sec
        self.velocity_y = max(MAX_RISE_SPEED, min(MAX_FALL_SPEED, self.velocity_y))

        self.y += self.velocity_y * dt_sec
        self.rect.y = int(self.y)

        self.flap_state_timer_ms = max(0, self.flap_state_timer_ms - dt_ms)
        self._set_state("active" if self.flap_state_timer_ms > 0 else "idle")
        self._update_animation(dt_ms)

class Obstacle(pygame.sprite.Sprite):
    _texture_cache = None

    def __init__(self, x, is_top, gap_y, gap_size, dynamic_amp=0.0, dynamic_omega=0.0, dynamic_phase=0.0):
        super().__init__()
        self.is_top = is_top
        self.gap_y = float(gap_y)
        self.gap_size = gap_size

        # Dynamic obstacle motion parameters (vertical oscillation).
        self.dynamic_amp = float(dynamic_amp)
        self.dynamic_omega = float(dynamic_omega)
        self.dynamic_phase = float(dynamic_phase)
        self.time_sec = 0.0

        if is_top:
            segment_height = max(20, gap_y - gap_size // 2)
        else:
            segment_height = max(20, SCREEN_HEIGHT - (gap_y + gap_size // 2))

        base_texture = self._get_texture()
        self.image = pygame.transform.smoothscale(base_texture, (OBSTACLE_WIDTH, segment_height))

        if is_top:
            self.rect = self.image.get_rect(bottomleft=(x, gap_y - gap_size // 2))
        else:
            self.rect = self.image.get_rect(topleft=(x, gap_y + gap_size // 2))

        self.float_x = float(self.rect.x)
        self.base_y = float(self.rect.y)

    @classmethod
    def _get_texture(cls):
        if cls._texture_cache is not None:
            return cls._texture_cache

        try:
            cls._texture_cache = pygame.image.load(OBSTACLE_IMAGE).convert_alpha()
        except pygame.error:
            fallback = pygame.Surface((OBSTACLE_WIDTH, 200), pygame.SRCALPHA)
            fallback.fill((50, 200, 50))
            cls._texture_cache = fallback
        return cls._texture_cache

    def update(self, speed, dt_ms):
        dt_sec = dt_ms / 1000.0
        self.float_x -= speed
        self.rect.x = int(self.float_x)

        self.time_sec += dt_sec
        if self.dynamic_amp > 0.0:
            y_offset = self.dynamic_amp * math.sin(self.dynamic_omega * self.time_sec + self.dynamic_phase)
            self.rect.y = int(self.base_y + y_offset)

        if self.rect.right < 0:
            self.kill()  # Despawn to free memory.


class Collectible(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.frames = self._load_frames(COLLECTIBLE_FRAME_PATHS)
        self.index = 0
        self.image = self.frames[self.index]
        self.rect = self.image.get_rect(center=(x, y))
        self.float_x = float(self.rect.x)
        self.anim_timer_ms = 0

    def _load_frames(self, image_paths):
        frames = []
        for i, path in enumerate(image_paths):
            try:
                frame = pygame.image.load(path).convert_alpha()
                frame = pygame.transform.smoothscale(frame, (30, 30))
            except pygame.error:
                # Fallback spinning coin-like silhouette if image is not provided yet.
                frame = pygame.Surface((30, 30), pygame.SRCALPHA)
                width = max(6, 30 - (i * 5))
                pygame.draw.ellipse(frame, (255, 215, 0), (15 - width // 2, 0, width, 30))
            frames.append(frame)
        return frames

    def update(self, speed, dt_ms):
        self.float_x -= speed
        self.rect.x = int(self.float_x)

        self.anim_timer_ms += dt_ms
        while self.anim_timer_ms >= COIN_ANIM_INTERVAL_MS:
            self.anim_timer_ms -= COIN_ANIM_INTERVAL_MS
            self.index = (self.index + 1) % len(self.frames)
            self.image = self.frames[self.index]

        if self.rect.right < 0:
            self.kill()


class Particle:
    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self.vx = random.uniform(-220, -120)
        self.vy = random.uniform(-120, 120)
        self.life_ms = PARTICLE_LIFETIME_MS
        self.max_life_ms = PARTICLE_LIFETIME_MS
        self.size = random.randint(2, 5)
        self.color = random.choice([
            (245, 245, 245),
            (225, 225, 225),
            (255, 220, 180),
        ])

    def update(self, dt_ms):
        dt_sec = dt_ms / 1000.0
        self.life_ms -= dt_ms
        self.x += self.vx * dt_sec
        self.y += self.vy * dt_sec
        self.vy += 420.0 * dt_sec

    def draw(self, screen):
        if self.life_ms <= 0:
            return
        alpha = max(0.0, self.life_ms / self.max_life_ms)
        radius = max(1, int(self.size * alpha))
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), radius)

    @property
    def alive(self):
        return self.life_ms > 0


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Arial", 40)
        
        # Adjustable Settings
        self.base_speed = 4.0 
        self.state = STATE_MENU
        self.reset_game()

        # UI Buttons
        self.start_btn = Button("START GAME", 300, 250, 200, 60, (0, 150, 0), (0, 200, 0))
        self.settings_btn = Button("SETTINGS", 300, 330, 200, 60, (100, 100, 100), (150, 150, 150))
        self.restart_btn = Button("RESTART", 300, 350, 200, 60, (200, 50, 50), (255, 80, 80))
        self.speed_up_btn = Button("SPEED +", 420, 300, 120, 50, (50, 50, 200), (80, 80, 255))
        self.speed_down_btn = Button("SPEED -", 260, 300, 120, 50, (50, 50, 200), (80, 80, 255))
        self.back_btn = Button("BACK", 340, 450, 120, 50, (100, 100, 100), (150, 150, 150))

    def reset_game(self):
        """Resets all game variables for a fresh start/restart."""
        self.score = 0
        self.current_speed = self.base_speed
        self.difficulty_time_sec = 0.0
        self.difficulty_multiplier = 1.0
        self.player = pygame.sprite.GroupSingle(Player())
        self.obstacles = pygame.sprite.Group()
        self.spawn_timer_ms = 0
        self.collectibles = pygame.sprite.Group()
        self.particles = []
        # 3-layer parallax setup
        # Layer 1: Sky/Clouds (slowest)
        # Layer 2: Mountains/Cityscape (medium)
        # Layer 3: Ground/Foreground (fastest, matches obstacle speed)
        self.layers = [
            BackgroundLayer(LAYER1_IMAGE, 0.2, 0, SCREEN_HEIGHT, (130, 190, 245)),
            BackgroundLayer(LAYER2_IMAGE, 0.55, 250, 300, (95, 110, 135)),
            BackgroundLayer(LAYER3_IMAGE, 1.0, 540, 60, (90, 170, 90)),
        ]

    def draw_text(self, text, y, size=40):
        surf = pygame.font.SysFont("Arial", size).render(text, True, (255, 255, 255))
        rect = surf.get_rect(center=(SCREEN_WIDTH//2, y))
        self.screen.blit(surf, rect)

    def _check_game_over_collision(self):
        player_sprite = self.player.sprite
        if player_sprite is None:
            return False

        # AABB collision checks against all obstacle rects.
        hit_obstacle = pygame.sprite.spritecollideany(player_sprite, self.obstacles) is not None
        hit_ground = player_sprite.rect.bottom >= SCREEN_HEIGHT
        hit_ceiling = player_sprite.rect.top <= 0
        return hit_obstacle or hit_ground or hit_ceiling

    def _collect_collectibles(self):
        player_sprite = self.player.sprite
        if player_sprite is None:
            return

        collected = pygame.sprite.spritecollide(player_sprite, self.collectibles, True)
        if collected:
            self.score += COLLECTIBLE_SCORE * len(collected)

    def _spawn_flap_particles(self):
        player_sprite = self.player.sprite
        if player_sprite is None:
            return

        origin_x = player_sprite.rect.left + 4
        origin_y = player_sprite.rect.centery
        for _ in range(PARTICLE_SPAWN_PER_FLAP):
            self.particles.append(Particle(origin_x, origin_y))

    def _update_particles(self, dt_ms):
        for p in self.particles:
            p.update(dt_ms)
        self.particles = [p for p in self.particles if p.alive]

    def _draw_particles(self):
        for p in self.particles:
            p.draw(self.screen)

    def _update_difficulty(self, dt_ms):
        self.difficulty_time_sec += dt_ms / 1000.0
        scaled = 1.0 + self.difficulty_time_sec * DIFFICULTY_RAMP_PER_SEC
        self.difficulty_multiplier = min(MAX_DIFFICULTY_MULTIPLIER, scaled)
        self.current_speed = self.base_speed * self.difficulty_multiplier

    def _spawn_obstacle_and_collectible(self):
        # Difficulty affects gap size and obstacle movement intensity.
        difficulty_ratio = (self.difficulty_multiplier - 1.0) / (MAX_DIFFICULTY_MULTIPLIER - 1.0)
        difficulty_ratio = max(0.0, min(1.0, difficulty_ratio))

        dynamic_gap_max = int(MAX_GAP_SIZE - 70 * difficulty_ratio)
        gap_size = random.randint(MIN_GAP_SIZE, max(MIN_GAP_SIZE + 5, dynamic_gap_max))
        gap_y = random.randint(150, 450)

        amp = random.uniform(DYNAMIC_OBSTACLE_MIN_AMPLITUDE, DYNAMIC_OBSTACLE_MAX_AMPLITUDE)
        omega = random.uniform(DYNAMIC_OBSTACLE_MIN_ANGULAR_SPEED, DYNAMIC_OBSTACLE_MAX_ANGULAR_SPEED)
        phase = random.uniform(0.0, 2.0 * math.pi)

        spawn_x = SCREEN_WIDTH + 50
        top = Obstacle(spawn_x, True, gap_y, gap_size, amp, omega, phase)
        bot = Obstacle(spawn_x, False, gap_y, gap_size, amp, omega, phase)
        self.obstacles.add(top)
        self.obstacles.add(bot)

        collectible_y = random.randint(gap_y - gap_size // 3, gap_y + gap_size // 3)
        self.collectibles.add(Collectible(SCREEN_WIDTH + 150, collectible_y))

    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                
                if self.state == STATE_MENU:
                    if self.start_btn.is_clicked(event): self.state = STATE_PLAYING
                    if self.settings_btn.is_clicked(event): self.state = STATE_SETTINGS
                
                elif self.state == STATE_SETTINGS:
                    if self.speed_up_btn.is_clicked(event): self.base_speed += 1
                    if self.speed_down_btn.is_clicked(event): self.base_speed = max(2, self.base_speed - 1)
                    if self.back_btn.is_clicked(event): self.state = STATE_MENU
                
                elif self.state == STATE_PLAYING:
                    pass
                
                elif self.state == STATE_GAMEOVER:
                    if self.restart_btn.is_clicked(event):
                        self.reset_game()
                        self.state = STATE_PLAYING

            self.screen.fill((135, 206, 235))

            if self.state == STATE_MENU:
                self.draw_text("INFINITE FLYER", 150, 60)
                self.start_btn.draw(self.screen)
                self.settings_btn.draw(self.screen)

            elif self.state == STATE_SETTINGS:
                self.draw_text("SETTINGS", 100)
                self.draw_text(f"Starting Speed: {self.base_speed}", 230, 30)
                self.speed_up_btn.draw(self.screen)
                self.speed_down_btn.draw(self.screen)
                self.back_btn.draw(self.screen)

            elif self.state == STATE_PLAYING:
                # Mechanics
                self._update_difficulty(dt)
                for layer in self.layers: 
                    layer.update(self.current_speed); layer.draw(self.screen)

                flap_requested = False
                for event in events:
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        flap_requested = True
                        self._spawn_flap_particles()
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        flap_requested = True
                        self._spawn_flap_particles()
                
                # Time-based spawning so behavior is stable across frame rates.
                self.spawn_timer_ms += dt
                spawn_interval = max(650, int(OBSTACLE_SPAWN_INTERVAL_MS / self.difficulty_multiplier))
                while self.spawn_timer_ms >= spawn_interval:
                    self._spawn_obstacle_and_collectible()
                    self.spawn_timer_ms -= spawn_interval

                # --- Update & Draw Collectibles ---
                self.collectibles.update(self.current_speed, dt)
                self.collectibles.draw(self.screen)

                # --- Particle system ---
                self._update_particles(dt)
                self._draw_particles()

                # --- Collision Detection for Collectibles ---
                self._collect_collectibles()

                self.player.update(dt, flap_requested)
                self.obstacles.update(self.current_speed, dt)

                # Collision [cite: 53, 54]
                if self._check_game_over_collision():
                    self.state = STATE_GAMEOVER

                self.obstacles.draw(self.screen)
                self.player.draw(self.screen)
                self.draw_text(f"SCORE: {self.score}", 50) # Live score display 

            elif self.state == STATE_GAMEOVER:
                self.draw_text("GAME OVER", 200, 60)
                self.draw_text(f"FINAL SCORE: {self.score}", 280, 30)
                self.restart_btn.draw(self.screen)

            pygame.display.flip()

if __name__ == "__main__":
    Game().run()
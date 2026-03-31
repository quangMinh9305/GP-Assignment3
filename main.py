import pygame
import random
import sys

# --- Configuration & Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
GRAVITY = 0.5
FLAP_STRENGTH = -8

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
    def __init__(self, image_path, speed_multiplier, y_pos, height):
        self.speed_multiplier = speed_multiplier
        self.y_pos = y_pos
        
        try:
            # Load the image and ensure it handles transparency
            raw_image = pygame.image.load(image_path).convert_alpha()
            # Scale the image to fit the screen width while keeping your specified height
            self.image = pygame.transform.scale(raw_image, (SCREEN_WIDTH, height))
        except pygame.error as e:
            print(f"Unable to load image: {image_path} - {e}")
            # Fallback to a placeholder if the file is missing
            self.image = pygame.Surface((SCREEN_WIDTH, height))
            self.image.fill((200, 0, 200)) 

        self.width = SCREEN_WIDTH
        self.x1, self.x2 = 0, self.width

    def update(self, global_speed):
        move_speed = global_speed * self.speed_multiplier
        self.x1 -= move_speed
        self.x2 -= move_speed
        # Seamless scrolling logic
        if self.x1 <= -self.width: self.x1 = self.x2 + self.width
        if self.x2 <= -self.width: self.x2 = self.x1 + self.width

    def draw(self, screen):
        screen.blit(self.image, (self.x1, self.y_pos))
        screen.blit(self.image, (self.x2, self.y_pos))

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        # Frame-based animation requirement [cite: 25, 40]
        self.frames = [pygame.Surface((40, 30)) for _ in range(3)]
        for i, f in enumerate(self.frames): f.fill((255, 100, 100))
        self.index = 0
        self.image = self.frames[self.index]
        self.rect = self.image.get_rect(center=(150, 300))
        self.velocity = 0
        self.anim_timer = 0

    def flap(self): self.velocity = FLAP_STRENGTH # Impulse physics [cite: 39]

    def update(self, dt):
        self.velocity += GRAVITY
        self.rect.y += self.velocity
        self.anim_timer += dt
        if self.anim_timer > 150: # Update based on time, not frames [cite: 43]
            self.index = (self.index + 1) % len(self.frames)
            self.image = self.frames[self.index]
            self.anim_timer = 0

class Obstacle(pygame.sprite.Sprite):
    def __init__(self, x, is_top, gap_y, gap_size):
        super().__init__()
        self.image = pygame.Surface((70, SCREEN_HEIGHT))
        self.image.fill((50, 200, 50))
        if is_top: self.rect = self.image.get_rect(bottomleft=(x, gap_y - gap_size//2))
        else: self.rect = self.image.get_rect(topleft=(x, gap_y + gap_size//2))

    def update(self, speed):
        self.rect.x -= speed
        if self.rect.right < 0: self.kill() # Memory management [cite: 51]
class Collectible(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        # Create 4 frames for a "spinning" effect
        self.frames = []
        for i in range(4):
            surf = pygame.Surface((30, 30), pygame.SRCALPHA)
            # Draw a shrinking/growing yellow circle to simulate spinning
            width = 30 - (i * 5) 
            pygame.draw.ellipse(surf, (255, 215, 0), (15 - width//2, 0, width, 30))
            self.frames.append(surf)
        
        self.index = 0
        self.image = self.frames[self.index]
        self.rect = self.image.get_rect(center=(x, y))
        self.anim_timer = 0

    def update(self, speed, dt):
        # Move left
        self.rect.x -= speed
        
        # Looping Animation
        self.anim_timer += dt
        if self.anim_timer > 100: # Change frame every 100ms
            self.index = (self.index + 1) % len(self.frames)
            self.image = self.frames[self.index]
            self.anim_timer = 0
            
        # Memory Management: Remove if off-screen
        if self.rect.right < 0:
            self.kill()
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
        self.player = pygame.sprite.GroupSingle(Player())
        self.obstacles = pygame.sprite.Group()
        self.spawn_timer = 0
        self.collectibles = pygame.sprite.Group()
        # Parallax setup using images instead of colors
        # BackgroundLayer(path, speed, y_position, height)
        self.layers = [
            BackgroundLayer("sky.png", 0.2, 0, SCREEN_HEIGHT),       # Far background (moves slowest)
            BackgroundLayer("mount.jpg", 0.5, 250, 300),         # Midground
            BackgroundLayer("ground.jpg", 1.0, 550, 50)             # Foreground (moves fastest)
        ]

    def draw_text(self, text, y, size=40):
        surf = pygame.font.SysFont("Arial", size).render(text, True, (255, 255, 255))
        rect = surf.get_rect(center=(SCREEN_WIDTH//2, y))
        self.screen.blit(surf, rect)

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
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                        self.player.sprite.flap()
                
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
                self.current_speed += 0.001 # Difficulty scaling 
                for layer in self.layers: 
                    layer.update(self.current_speed); layer.draw(self.screen)
                
                self.spawn_timer += 1
                if self.spawn_timer > 100:
                    # 1. Randomized vertical positions and varying gap sizes
                    gap_y = random.randint(150, 450)
                    gap_size = random.randint(150, 250) # Varying gap size
                    
                    # Spawn Obstacles
                    self.obstacles.add(Obstacle(SCREEN_WIDTH + 50, True, gap_y, gap_size))
                    self.obstacles.add(Obstacle(SCREEN_WIDTH + 50, False, gap_y, gap_size))
                    
                    # 2. Spawn Collectibles in tandem (placed in the middle of the gap)
                    if random.random() > 0.5: # 50% chance to spawn a coin
                        self.collectibles.add(Collectible(SCREEN_WIDTH + 150, gap_y))
                    
                    self.spawn_timer = 0

                # --- Update & Draw Collectibles ---
                self.collectibles.update(self.current_speed, dt)
                self.collectibles.draw(self.screen)

                # --- Collision Detection for Collectibles ---
                picked_up = pygame.sprite.spritecollide(self.player.sprite, self.collectibles, True)
                if picked_up:
                    self.score += 5 # Bonus points for collectibles

                self.player.update(dt)
                self.obstacles.update(self.current_speed)

                # Collision [cite: 53, 54]
                if pygame.sprite.spritecollide(self.player.sprite, self.obstacles, False) or \
                   self.player.sprite.rect.bottom > SCREEN_HEIGHT or self.player.sprite.rect.top < 0:
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
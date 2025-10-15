def __init__(self, name, color, hp, position):
    self.name = name
    self.color = color
    self.hp = hp
    self.position = position

def move(self, new_position):
    self.position = new_position

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.die()

    def die(self):
        print(f"{self.name} has been defeated.")
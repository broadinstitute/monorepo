{
  description = "A collection of flake templates";

  outputs = { self }: {
    templates = {
      portrait = {
        path = ./libs/jump_portrait;
        description = "JUMP portrait development template";
      };

    };

  };
}

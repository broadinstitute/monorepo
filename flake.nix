{
  description = "A collection of flake templates";

  outputs = { self }: {
    templates = {
      trivial = {
        path = ./libs/jump_portrait;
        description = "A very basic flake";
      };

    };

  };
}
